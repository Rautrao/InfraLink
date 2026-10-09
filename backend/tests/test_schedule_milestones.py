from conftest import login
from test_project_registry import create_work

def test_revision_reason_and_milestone_progress(client):
    token=login(client,"je.ward1@demo.city")
    work=create_work(client,token,"Schedule test work").json()
    headers={"Authorization":f"Bearer {token}"}
    date_url=f"/api/v1/works/{work['id']}/dates"
    too_short=client.post(date_url,headers=headers,json={"new_target_end":"2026-11-24","reason_code":"weather","explanation":"Rain"})
    assert too_short.status_code==422
    unknown=client.post(date_url,headers=headers,json={"new_target_end":"2026-11-24","reason_code":"unknown","explanation":"Materials need extra delivery time."})
    assert unknown.status_code==422
    revised=client.post(date_url,headers=headers,json={"new_target_end":"2026-11-24","reason_code":"material_delay","explanation":"The supplier confirmed a later delivery date."})
    assert revised.status_code==200 and revised.json()["old_target"]=="2026-11-20"
    detail=client.get(f"/api/v1/works/{work['id']}").json()
    assert detail["original_target_end"]=="2026-11-20" and detail["current_target_end"]=="2026-11-24"
    first=client.post(f"/api/v1/works/{work['id']}/milestones",headers=headers,json={"name":"Trenching","planned_date":"2026-11-05","pct":40})
    second=client.post(f"/api/v1/works/{work['id']}/milestones",headers=headers,json={"name":"Pipe laying","planned_date":"2026-11-10","pct":50})
    assert first.status_code==second.status_code==201
    done=client.patch(f"/api/v1/milestones/{first.json()['id']}",headers=headers,json={"actual_date":"2026-11-05"})
    assert done.status_code==200 and done.json()["pct"]==100
    updated=client.get(f"/api/v1/works/{work['id']}").json()
    assert updated["pct_complete"]==75
    timeline=client.get(f"/api/v1/works/{work['id']}/history").json()
    assert any(x["kind"]=="date_revision" for x in timeline["items"])

def test_schedule_changes_require_staff(client):
    denied=client.post("/api/v1/works/00000000-0000-0000-0000-000000000001/dates",json={"new_target_end":"2026-12-01","reason_code":"other","explanation":"The schedule needs an update."})
    assert denied.status_code==401
