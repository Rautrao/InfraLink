from conftest import login

LINE = {"type": "LineString", "coordinates": [[73.8500, 18.5100], [73.8540, 18.5120]]}

def create_work(client, token, title="Test water work"):
    agency_id = next(a["id"] for a in client.get("/api/v1/agencies").json() if a["short_code"] == "ROADS")
    return client.post("/api/v1/works", headers={"Authorization": f"Bearer {token}"}, json={
        "title": title, "purpose": "Replace a worn public service line", "category": "water_pipeline",
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
    timeline = client.get(f"/api/v1/works/{work['id']}/history")
    assert timeline.status_code == 200 and any(event["kind"] == "update" for event in timeline.json()["items"])

def test_works_write_requires_staff_and_status_machine(client):
    response = create_work(client, "invalid-token")
    assert response.status_code == 401
    token = login(client, "je.ward1@demo.city")
    work = create_work(client, token, "Status test work").json()
    url = f"/api/v1/works/{work['id']}/status"
    rejected = client.post(url, headers={"Authorization": f"Bearer {token}"}, json={"to_status":"paused"})
    assert rejected.status_code == 422
    paused = client.post(url, headers={"Authorization": f"Bearer {token}"}, json={"to_status":"paused","reason_code":"utility_clash","explanation":"Work paused while the adjacent service alignment is reviewed."})
    assert paused.status_code == 200 and paused.json()["status"] == "paused"
