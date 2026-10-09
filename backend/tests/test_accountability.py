from conftest import login
from test_project_registry import create_work
from app.core import clock
from app.core.db import SessionLocal
from app.modules.notifications.router import _deliver

LINE={"type":"LineString","coordinates":[[73.8200,18.5100],[73.8240,18.5120]]}

def resident_token(client,phone="9000000001"):
    assert client.post("/api/v1/auth/otp/request",json={"phone":phone}).status_code==200
    response=client.post("/api/v1/auth/otp/verify",json={"phone":phone,"otp":"123456"})
    assert response.status_code==200,response.text
    return response.json()["access_token"]

def test_feedback_escalates_across_3_7_14_day_slas(client):
    start=clock.now()
    try:
        staff=login(client,"je.ward1@demo.city")
        work=create_work(client,staff,"Feedback SLA escalation").json()
        resident=resident_token(client)
        headers={"Authorization":f"Bearer {resident}"}
        submitted=client.post(f"/api/v1/works/{work['id']}/feedback",headers=headers,data={"kind":"complaint","text":"The roadside trench is still open and needs a safe cover."})
        assert submitted.status_code==201,submitted.text
        ref=submitted.json()["ref_no"]
        assert ref.startswith(f"FB-{clock.now().year}-")

        assert client.post("/api/v1/dev/advance-time",json={"days":3}).status_code==200
        at_ae=client.get("/api/v1/staff/feedback?awaiting=true&level=2",headers={"Authorization":f"Bearer {login(client)}"}).json()["items"]
        assert any(ticket["ref_no"]==ref for ticket in at_ae)

        assert client.post("/api/v1/dev/advance-time",json={"days":7}).status_code==200
        at_ee=client.get("/api/v1/staff/feedback?awaiting=true&level=3",headers={"Authorization":f"Bearer {login(client)}"}).json()["items"]
        assert any(ticket["ref_no"]==ref for ticket in at_ee)

        assert client.post("/api/v1/dev/advance-time",json={"days":14}).status_code==200
        at_se=client.get("/api/v1/staff/feedback?awaiting=true&level=4",headers={"Authorization":f"Bearer {login(client)}"}).json()["items"]
        ticket=next(ticket for ticket in at_se if ticket["ref_no"]==ref)
        assert ticket["overdue_public"] is True
        assert [event["message"] for event in ticket["history"] if event["message"] and event["message"].startswith("Escalated")] == [
            "Escalated to level 2 after SLA elapsed.","Escalated to level 3 after SLA elapsed.","Escalated to level 4 after SLA elapsed."]
    finally:
        elapsed=(clock.now()-start).days
        if elapsed: client.post("/api/v1/dev/advance-time",json={"days":-elapsed})

def test_noncritical_notifications_dedupe_into_one_daily_digest(client):
    staff=login(client,"je.ward1@demo.city")
    work=create_work(client,staff,"Notification digest").json()
    resident=resident_token(client,"9000000002")
    headers={"Authorization":f"Bearer {resident}"}
    followed=client.post("/api/v1/follows",headers=headers,json={"work_id":work["id"],"channel":"console"})
    assert followed.status_code==201,followed.text
    with SessionLocal() as db:
        payload={"work_id":work["id"],"occurred_at":clock.now().isoformat(),"event_id":900001}
        assert _deliver(db,"WorkCreated.v1",payload)==1
        db.commit()
        payload["event_id"]=900002
        assert _deliver(db,"WorkUpdated.v1",{**payload,"changed_fields":["title"]})==0
        payload["event_id"]=900003
        assert _deliver(db,"WorkUpdated.v1",{**payload,"changed_fields":["geometry"]})==1
        db.commit()
    notifications=client.get("/api/v1/notifications/mine",headers=headers).json()["items"]
    digest=[item for item in notifications if item["kind"]=="daily_digest"]
    assert len(digest)==1
    assert digest[0]["link"]==f"/works/{work['id']}"
    assert "Notification digest" in digest[0]["body"]

def test_feedback_publication_requires_moderation_and_redacts_resident_details(client):
    staff=login(client,"je.ward1@demo.city")
    work=create_work(client,staff,"Feedback moderation").json()
    resident=resident_token(client,"9000000003")
    response=client.post(f"/api/v1/works/{work['id']}/feedback",headers={"Authorization":f"Bearer {resident}"},data={"kind":"observation","text":"Please call Resident 3 at 9000000003 about this."})
    assert response.status_code==201,response.text
    ref=response.json()["ref_no"]
    assert client.get(f"/api/v1/works/{work['id']}/feedback/public").json()["items"]==[]
    ticket_id=response.json()["id"]
    moderated=client.post(f"/api/v1/staff/feedback/{ticket_id}/moderate",headers={"Authorization":f"Bearer {staff}"},json={"approve":True})
    assert moderated.status_code==200
    public=client.get(f"/api/v1/works/{work['id']}/feedback/public").json()["items"]
    assert len(public)==1 and public[0]["ref_no"]==ref
    assert "9000000003" not in public[0]["text"] and "Resident 3" not in public[0]["text"]

def test_conflict_resolution_releases_permit_coordination_hold(client):
    engineer=login(client,"je.ward1@demo.city")
    work_a=create_work(client,engineer,"Permit conflict A").json()
    work_b=create_work(client,engineer,"Permit conflict B").json()
    admin=login(client)
    admin_headers={"Authorization":f"Bearer {admin}"}
    scan=client.post("/api/v1/conflicts/scan",headers=admin_headers)
    assert scan.status_code==200,scan.text
    conflicts=client.get("/api/v1/conflicts?status=open",headers=admin_headers).json()["items"]
    conflict=next(item for item in conflicts if {item["work_a"]["id"],item["work_b"]["id"]}=={work_a["id"],work_b["id"]})
    detail=client.get(f"/api/v1/conflicts/{conflict['id']}",headers=admin_headers)
    assert detail.status_code==200 and detail.json()["work_a"]["geometry"] and detail.json()["buffer_geometry_a"]

    submitted=client.post("/api/v1/permits",headers=admin_headers,json={"work_id":work_a["id"],"type":"road_cut","valid_from":"2026-11-01","valid_to":"2026-11-20","deposit_amount":25000})
    assert submitted.status_code==201,submitted.text
    permit_id=submitted.json()["id"]
    assert submitted.json()["status"]=="pending_coordination"
    blocked=client.post(f"/api/v1/permits/{permit_id}/decision",headers=admin_headers,json={"action":"approve","note":"Please approve this permit today."})
    assert blocked.status_code==409 and blocked.json()["error"]["code"]=="PENDING_COORDINATION"
    decided=client.post(f"/api/v1/conflicts/{conflict['id']}/decision",headers=admin_headers,json={"action":"justify_both","note":"Both work crews have independent signed traffic plans."})
    assert decided.status_code==200
    ready=client.get(f"/api/v1/permits/{permit_id}",headers=admin_headers).json()
    assert ready["status"]=="submitted"
    executive=login(client,"ee.roads@demo.city")
    approved=client.post(f"/api/v1/permits/{permit_id}/decision",headers={"Authorization":f"Bearer {executive}"},json={"action":"approve","note":"Approved after coordination review."})
    assert approved.status_code==200 and approved.json()["status"]=="approved"

def test_reporting_and_open_data_contract(client):
    admin={"Authorization":f"Bearer {login(client)}"}
    assert client.get("/api/v1/reports/summary").status_code==200
    for path in ("/api/v1/reports/delayed","/api/v1/reports/overdue-updates","/api/v1/reports/repeat-dig","/api/v1/staff/inbox"):
        response=client.get(path,headers=admin)
        assert response.status_code==200,(path,response.text)

    geo=client.get("/api/v1/open/works.geojson")
    assert geo.status_code==200 and geo.headers["cache-control"]=="public, max-age=60"
    assert geo.headers["access-control-allow-origin"]=="*" and geo.headers.get("last-modified")
    if geo.json()["features"]:
        properties=geo.json()["features"][0]["properties"]
        assert "contact_phone" not in properties and "contact_email" not in properties and "deposit_amount" not in properties
    assert "ref_no,title" in client.get("/api/v1/open/works.csv").text
    assert client.get("/api/v1/open/stats.json").status_code==200
