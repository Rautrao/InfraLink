import hashlib
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from app.core.db import get_db
from app.core.security import require_roles

router=APIRouter()
AUDIT_ROLES=("auditor","admin","commissioner")

def _canonical(row):
    body={
        "tenant_id":str(row["tenant_id"]),
        "actor_id":str(row["actor_id"]) if row["actor_id"] else None,
        "action":row["action"],"entity":row["entity"],
        "entity_id":str(row["entity_id"]) if row["entity_id"] is not None else None,
        "before":row["before"],"after":row["after"],"at":row["at"].isoformat(),
    }
    return json.dumps(body,sort_keys=True,separators=(",",":"),default=str)

@router.get("/audit/ping")
def ping(): return {"module":"audit","status":"ready"}

@router.get("/audit")
def list_audit(entity: str|None=None,entity_id: str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db=Depends(get_db),user=Depends(require_roles(*AUDIT_ROLES))):
    conditions=["tenant_id=cast(:tenant as uuid)"]; params={"tenant":str(user["tenant_id"])}
    if entity:
        conditions.append("entity=:entity"); params["entity"]=entity
    if entity_id:
        conditions.append("entity_id=:entity_id"); params["entity_id"]=entity_id
    condition=" and ".join(conditions)
    total=db.execute(text(f"select count(*) from audit_log where {condition}"),params).scalar() or 0
    rows=db.execute(text(f"select id,actor_id,action,entity,entity_id,before,after,at,prev_hash,hash from audit_log where {condition} order by id desc limit :limit offset :offset"),{**params,"limit":page_size,"offset":(page-1)*page_size}).mappings().all()
    return {"items":[dict(r) for r in rows],"total":total,"page":page,"page_size":page_size}

@router.get("/audit/verify")
def verify_audit(db=Depends(get_db),user=Depends(require_roles(*AUDIT_ROLES))):
    rows=db.execute(text("select id,tenant_id,actor_id,action,entity,entity_id,before,after,at,prev_hash,hash from audit_log where tenant_id=cast(:tenant as uuid) order by id"),{"tenant":str(user["tenant_id"])}).mappings().all()
    previous="0"*64
    for row in rows:
        if row["prev_hash"]!=previous:
            return {"valid":False,"broken_at":row["id"]}
        expected=hashlib.sha256((previous+_canonical(row)).encode()).hexdigest()
        if row["hash"]!=expected:
            return {"valid":False,"broken_at":row["id"]}
        previous=row["hash"]
    return {"valid":True,"broken_at":None}
