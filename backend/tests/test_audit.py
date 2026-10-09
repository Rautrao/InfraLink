import uuid
from sqlalchemy import text
from conftest import login
from app.core.db import engine
from app.core.db import SessionLocal
from app.core.security import create_token
from app.core.audit import write_audit

def fresh_audit_tenant():
    tenant_id=uuid.uuid4(); user_id=uuid.uuid4()
    with SessionLocal() as session:
        session.execute(text("insert into tenant(id,name,slug) values (:id,'Audit test',:slug)"),{"id":tenant_id,"slug":f"audit-{tenant_id}"})
        session.execute(text("insert into app_user(id,tenant_id,name,role,active) values (:id,:tenant,'Audit tester','admin',true)"),{"id":user_id,"tenant":tenant_id})
        actor={"id":user_id,"tenant_id":tenant_id,"role":"admin"}
        write_audit(session,actor,"test_created","audit_test","row-1",after={"ok":True})
        session.commit()
    return str(tenant_id),str(user_id),create_token({"id":user_id,"tenant_id":tenant_id,"role":"admin"})

def test_audit_list_and_verify(client):
    tenant_id,user_id,token=fresh_audit_tenant()
    headers={"Authorization":f"Bearer {token}"}
    audit=client.get("/api/v1/audit?page=1&page_size=5",headers=headers)
    assert audit.status_code==200 and audit.json()["total"]==1
    verify=client.get("/api/v1/audit/verify",headers=headers)
    assert verify.status_code==200 and verify.json()=={"valid":True,"broken_at":None}

def test_audit_requires_auditor_or_admin(client):
    token=login(client,"je.ward1@demo.city")
    response=client.get("/api/v1/audit",headers={"Authorization":f"Bearer {token}"})
    assert response.status_code==403

def test_audit_verify_detects_superuser_tampering(client):
    tenant_id,user_id,token=fresh_audit_tenant()
    headers={"Authorization":f"Bearer {token}"}
    with engine.begin() as conn:
        audit_id=conn.execute(text("select id from audit_log where tenant_id=cast(:tenant as uuid)"),{"tenant":tenant_id}).scalar()
        assert audit_id is not None
        conn.execute(text("alter table audit_log disable trigger audit_log_no_update_delete"))
        conn.execute(text("update audit_log set action=action || ' tampered' where id=:id"),{"id":audit_id})
        conn.execute(text("alter table audit_log enable trigger audit_log_no_update_delete"))
    try:
        result=client.get("/api/v1/audit/verify",headers=headers)
        assert result.status_code==200
        assert result.json()=={"valid":False,"broken_at":audit_id}
    finally:
        with engine.begin() as conn:
            conn.execute(text("alter table audit_log disable trigger audit_log_no_update_delete"))
            conn.execute(text("update audit_log set action=regexp_replace(action,' tampered$','') where id=:id"),{"id":audit_id})
            conn.execute(text("alter table audit_log enable trigger audit_log_no_update_delete"))
