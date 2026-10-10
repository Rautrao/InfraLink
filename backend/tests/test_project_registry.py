from conftest import login

LINE = {"type": "LineString", "coordinates": [[73.8200, 18.5100], [73.8240, 18.5120]]}

def create_work(client, token, title="Test water work"):
    agency_id = next(a["id"] for a in client.get("/api/v1/agencies").json() if a["short_code"] == "ROADS")
    return client.post("/api/v1/works", headers={"Authorization": f"Bearer {token}"}, json={
        "title": f"TEST: {title}", "purpose": "Replace a worn public service line", "category": "water_pipeline",
        "agency_id": agency_id, "geometry": LINE, "planned_start": "2026-11-01",
        "original_target_end": "2026-11-20", "road_name": "MG Road",
        "contact_name": "Site Office", "contact_phone": "+919876540123", "contact_channel": "office",
    })

def test_create_read_geojson_and_update_work(client):
    token = login(client, "je.ward1@demo.city")
    created = create_work(client, token)
    assert created.status_code == 201, created.text
    work = created.json()
    assert work["status"] == "planned"
    assert work["original_target_end"] == work["current_target_end"] == "2026-11-20"
    assert work["length_m"] > 0 and work["ward"]
    public_work = client.get(f"/api/v1/works/{work['id']}").json()
    assert public_work["contact"]["phone_masked"] != "+919876540123"
    listed = client.get("/api/v1/works?road=MG%20Road")
    assert listed.status_code == 200 and listed.json()["total"] >= 1
    geo = client.get("/api/v1/works/geojson")
    assert geo.status_code == 200 and geo.json()["type"] == "FeatureCollection"
    response = client.patch(f"/api/v1/works/{work['id']}", headers={"Authorization": f"Bearer {token}"}, json={"current_target_end":"2026-11-25"})
    assert response.status_code == 422 and "use /works/{id}/dates" in response.json()["error"]["message"]
    response = client.patch(f"/api/v1/works/{work['id']}", headers={"Authorization": f"Bearer {token}"}, json={"disruption_type":"partial_closure","disruption_note":"Traffic uses the signed diversion"})
    assert response.status_code == 200
    assert response.json()["disruption"]["type"] == "partial_closure"
    posted = client.post(f"/api/v1/works/{work['id']}/updates", headers={"Authorization": f"Bearer {token}"}, json={"text":"Crew began trench preparation.","pct_complete":15})
    assert posted.status_code == 201
    decreased=client.post(f"/api/v1/works/{work['id']}/updates",headers={"Authorization":f"Bearer {token}"},json={"text":"Percentage correction","pct_complete":10})
    assert decreased.status_code==422
    timeline = client.get(f"/api/v1/works/{work['id']}/history")
    assert timeline.status_code == 200 and any(event["kind"] == "update" for event in timeline.json()["items"])

def test_resident_reads_only_public_work_and_sees_public_contact_fields(client):
    staff_token = login(client, "je.ward1@demo.city")
    created = create_work(client, staff_token, "Resident visibility test")
    work = created.json()
    resident = "9000000001"
    assert client.post("/api/v1/auth/otp/request", json={"phone": resident}).status_code == 200
    resident_token = client.post("/api/v1/auth/otp/verify", json={"phone": resident, "otp": "123456"}).json()["access_token"]
    resident_headers = {"Authorization": f"Bearer {resident_token}"}

    public_detail = client.get(f"/api/v1/works/{work['id']}", headers=resident_headers)
    assert public_detail.status_code == 200
    assert public_detail.json()["contact"]["phone_masked"] != "+919876540123"

    hidden = client.patch(f"/api/v1/works/{work['id']}", headers={"Authorization": f"Bearer {staff_token}"}, json={"is_public": False})
    assert hidden.status_code == 200
    assert client.get(f"/api/v1/works/{work['id']}", headers=resident_headers).status_code == 404
    visible = client.get("/api/v1/works", headers=resident_headers).json()
    assert work["id"] not in {item["id"] for item in visible["items"]}

def test_works_write_requires_staff_and_status_machine(client):
    response = create_work(client, "invalid-token")
    assert response.status_code == 401
    public_with_stale_token = client.get("/api/v1/works", headers={"Authorization": "Bearer invalid-token"})
    assert public_with_stale_token.status_code == 200
    public_geo_with_stale_token = client.get("/api/v1/works/geojson", headers={"Authorization": "Bearer invalid-token"})
    assert public_geo_with_stale_token.status_code == 200
    token = login(client, "je.ward1@demo.city")
    roads_id=next(a["id"] for a in client.get("/api/v1/agencies").json() if a["short_code"]=="ROADS")
    invalid=client.post("/api/v1/works",headers={"Authorization":f"Bearer {token}"},json={"title":"Invalid point geometry","category":"water_pipeline","agency_id":roads_id,"geometry":{"type":"Point","coordinates":[73.82,18.51]},"planned_start":"2026-11-01","original_target_end":"2026-11-20"})
    assert invalid.status_code==422
    outside=client.post("/api/v1/works",headers={"Authorization":f"Bearer {token}"},json={"title":"Out of ward","category":"water_pipeline","agency_id":roads_id,"geometry":{"type":"LineString","coordinates":[[73.8400,18.51],[73.8440,18.512]]},"planned_start":"2026-11-01","original_target_end":"2026-11-20"})
    assert outside.status_code==403
    work = create_work(client, token, "Status test work").json()
    url = f"/api/v1/works/{work['id']}/status"
    rejected = client.post(url, headers={"Authorization": f"Bearer {token}"}, json={"to_status":"paused"})
    assert rejected.status_code == 422
    paused = client.post(url, headers={"Authorization": f"Bearer {token}"}, json={"to_status":"paused","reason_code":"utility_clash","explanation":"Work paused while the adjacent service alignment is reviewed."})
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
    percent_work=create_work(client,token,"Completion percentage guard").json()
    percent_url=f"/api/v1/works/{percent_work['id']}/status"
    assert client.post(percent_url,headers={"Authorization":f"Bearer {token}"},json={"to_status":"permitted"}).status_code==200
    assert client.post(percent_url,headers={"Authorization":f"Bearer {token}"},json={"to_status":"ongoing"}).status_code==200
    assert client.post(percent_url,headers={"Authorization":f"Bearer {token}"},json={"to_status":"completed"}).status_code==409
