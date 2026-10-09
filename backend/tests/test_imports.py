import io
import json
from conftest import login
from sqlalchemy import text
from app.core.db import engine

def test_imports_ping(client):
    res = client.get("/api/v1/imports/ping")
    assert res.status_code == 200
    assert res.json()["module"] == "imports"

def test_import_template_download(client):
    res = client.get("/api/v1/works/import/template")
    assert res.status_code == 200
    assert "text/csv" in res.headers.get("content-type", "")
    assert "attachment" in res.headers.get("content-disposition", "")
    lines = res.text.strip().split("\n")
    header = lines[0].strip()
    expected_cols = [
        "title", "purpose", "category", "agency_code", "road_name",
        "planned_start", "original_target_end", "contractor_name",
        "contact_name", "contact_phone", "lat1", "lng1", "lat2", "lng2"
    ]
    for col in expected_cols:
        assert col in header

def test_import_csv_dry_run_and_actual(client):
    token = login(client, "admin@demo.city")
    headers = {"Authorization": f"Bearer {token}"}

    csv_content = (
        "title,purpose,category,agency_code,road_name,planned_start,original_target_end,contractor_name,contact_name,contact_phone,lat1,lng1,lat2,lng2\n"
        "TEST: Valid Import Work 1,Testing CSV import pipeline,water_pipeline,WATER,MG Road,2026-11-01,2026-11-20,Apex Infra,Site Office,+919876540001,18.5202,73.8350,18.5202,73.8392\n"
        ",Missing title work,water_pipeline,WATER,MG Road,2026-11-01,2026-11-20,Apex Infra,Site Office,+919876540001,18.5202,73.8350,18.5202,73.8392\n"
        "TEST: Bad Agency Work,Testing invalid agency,water_pipeline,INVALID_AGENCY,MG Road,2026-11-01,2026-11-20,Apex Infra,Site Office,+919876540001,18.5202,73.8350,18.5202,73.8392\n"
    )

    # 1. Dry run
    res_dry = client.post(
        "/api/v1/works/import?dry_run=true",
        headers=headers,
        files={"csv_file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    )
    assert res_dry.status_code == 200, res_dry.text
    dry_data = res_dry.json()
    assert len(dry_data["valid"]) == 1
    assert len(dry_data["invalid"]) == 2
    assert dry_data["valid"][0]["title"] == "TEST: Valid Import Work 1"
    # No ref_no should be assigned in dry_run
    assert "ref_no" not in dry_data["valid"][0]

    # Verify not inserted in DB
    with engine.begin() as conn:
        count = conn.execute(text("select count(*) from work where title='TEST: Valid Import Work 1'")).scalar()
        assert count == 0

    # 2. Actual import
    res_actual = client.post(
        "/api/v1/works/import?dry_run=false",
        headers=headers,
        files={"csv_file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    )
    assert res_actual.status_code == 200, res_actual.text
    actual_data = res_actual.json()
    assert len(actual_data["valid"]) == 1
    assert len(actual_data["invalid"]) == 2

    valid_work = actual_data["valid"][0]
    assert valid_work["title"] == "TEST: Valid Import Work 1"
    assert "id" in valid_work
    assert "ref_no" in valid_work
    assert valid_work["ref_no"].startswith("WRK-")

    # Verify inserted into work table
    with engine.begin() as conn:
        work_row = conn.execute(text("select id, ref_no, status, title from work where id=cast(:id as uuid)"), {"id": valid_work["id"]}).mappings().first()
        assert work_row is not None
        assert work_row["status"] == "planned"
        assert work_row["ref_no"] == valid_work["ref_no"]

        # Verify outbox event emitted
        event = conn.execute(text("select type, payload from outbox_event where payload->>'work_id'=:wid"), {"wid": valid_work["id"]}).mappings().first()
        assert event is not None
        assert event["type"] == "WorkCreated.v1"

        # Verify audit log recorded
        audit = conn.execute(text("select action, entity, entity_id, hash, prev_hash from audit_log where entity='work' and entity_id=:wid"), {"wid": valid_work["id"]}).mappings().first()
        assert audit is not None
        assert audit["action"] == "created"
        assert audit["hash"] is not None

def test_import_geojson_features(client):
    token = login(client, "admin@demo.city")
    headers = {"Authorization": f"Bearer {token}"}

    geojson_payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[73.8350, 18.5202], [73.8392, 18.5202]]
                },
                "properties": {
                    "title": "TEST: GeoJSON Water Work",
                    "purpose": "GeoJSON import test",
                    "category": "water_pipeline",
                    "agency_code": "WATER",
                    "road_name": "MG Road",
                    "planned_start": "2026-11-01",
                    "original_target_end": "2026-11-20",
                    "contractor_name": "Apex Infra",
                    "contact_name": "Site Office",
                    "contact_phone": "+919876540001"
                }
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[73.8350, 18.5202], [73.8392, 18.5202]]
                },
                "properties": {
                    "title": "TEST: GeoJSON Bad Category",
                    "purpose": "Invalid category test",
                    "category": "flying_carpet",
                    "agency_code": "WATER",
                    "road_name": "MG Road",
                    "planned_start": "2026-11-01",
                    "original_target_end": "2026-11-20"
                }
            }
        ]
    }

    raw_geojson = json.dumps(geojson_payload).encode("utf-8")
    res = client.post(
        "/api/v1/works/import?dry_run=false",
        headers=headers,
        files={"geojson_file": ("works.geojson", io.BytesIO(raw_geojson), "application/geo+json")}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["valid"]) == 1
    assert len(data["invalid"]) == 1
    assert data["valid"][0]["title"] == "TEST: GeoJSON Water Work"
    assert "flying_carpet" in str(data["invalid"][0]["errors"])

def test_import_validation_errors(client):
    token = login(client, "admin@demo.city")
    headers = {"Authorization": f"Bearer {token}"}

    # Missing file
    res = client.post("/api/v1/works/import", headers=headers)
    assert res.status_code == 400

    # Empty file
    res = client.post(
        "/api/v1/works/import",
        headers=headers,
        files={"csv_file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    )
    assert res.status_code == 400
