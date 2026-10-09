import csv
import hashlib
import io
import json
from datetime import date
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import text

from app.core import clock
from app.core.db import get_db
from app.core.events import emit
from app.core.security import get_optional_user
from app.modules.geo_spatial.service import locate_ward, length_m, validate_city_geometry

router = APIRouter()

VALID_CATEGORIES = {
    "road_cut",
    "resurfacing",
    "water_pipeline",
    "sewer",
    "drainage",
    "electricity",
    "telecom_duct",
    "gas_pipeline",
    "metro",
    "footpath",
    "other",
}

TEMPLATE_CSV = (
    "title,purpose,category,agency_code,road_name,planned_start,original_target_end,"
    "contractor_name,contact_name,contact_phone,lat1,lng1,lat2,lng2\n"
    "MG Road water pipeline trench,Replace a leaking main with a planned road restoration,"
    "water_pipeline,WATER,MG Road,2026-11-01,2026-11-20,Demo City Civil Works,"
    "Project Site Office,+919876540001,18.5202,73.8350,18.5202,73.8392\n"
    "Baner Road power cable renewal,Replace an underground power cable,"
    "electricity,POWER,Baner Road,2026-11-10,2026-12-05,Demo City Power Works,"
    "Project Site Office,+919876540002,18.5250,73.8690,18.5250,73.8715\n"
)


def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    if "T" in val_str:
        val_str = val_str.split("T")[0]
    elif " " in val_str:
        val_str = val_str.split(" ")[0]
    val_str = val_str.replace("/", "-")
    return date.fromisoformat(val_str)


def _write_audit_log(session, tenant_id, actor_id, action, entity, entity_id, before=None, after=None):
    at = clock.now()
    previous = session.execute(
        text("select hash from audit_log where tenant_id=cast(:tenant as uuid) order by id desc limit 1"),
        {"tenant": str(tenant_id)},
    ).scalar()
    previous = previous or "0" * 64
    body = {
        "tenant_id": str(tenant_id),
        "actor_id": str(actor_id) if actor_id else None,
        "action": action,
        "entity": entity,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "before": before,
        "after": after,
        "at": at.isoformat(),
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256((previous + canonical).encode()).hexdigest()
    session.execute(
        text("""
            insert into audit_log(tenant_id, actor_id, action, entity, entity_id, before, after, at, prev_hash, hash)
            values (cast(:tenant as uuid), cast(:actor as uuid), :action, :entity, :entity_id, cast(:before as jsonb), cast(:after as jsonb), :at, :prev, :hash)
        """),
        {
            "tenant": str(tenant_id),
            "actor": str(actor_id) if actor_id else None,
            "action": action,
            "entity": entity,
            "entity_id": str(entity_id),
            "before": json.dumps(before, default=str) if before is not None else None,
            "after": json.dumps(after, default=str) if after is not None else None,
            "at": at,
            "prev": previous,
            "hash": digest,
        },
    )


@router.get('/imports/ping')
def ping():
    return {'module': 'imports', 'status': 'scaffold'}


@router.get("/works/import/template")
def get_import_template():
    return Response(
        content=TEMPLATE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="works_template.csv"'},
    )


@router.post("/works/import")
async def import_works(
    csv_file: UploadFile | None = File(default=None),
    geojson_file: UploadFile | None = File(default=None),
    file: UploadFile | None = File(default=None),
    dry_run: bool = Query(default=False),
    db=Depends(get_db),
    user=Depends(get_optional_user),
):
    upload_file = None
    is_geojson = False

    if csv_file and csv_file.filename:
        upload_file = csv_file
        is_geojson = False
    elif geojson_file and geojson_file.filename:
        upload_file = geojson_file
        is_geojson = True
    elif file and file.filename:
        upload_file = file
        is_geojson = file.filename.lower().endswith((".geojson", ".json"))
    elif csv_file:
        upload_file = csv_file
        is_geojson = False
    elif geojson_file:
        upload_file = geojson_file
        is_geojson = True
    elif file:
        upload_file = file
        is_geojson = False
    else:
        raise HTTPException(400, "Either csv_file or geojson_file must be provided")

    content_bytes = await upload_file.read()
    if not content_bytes or not content_bytes.strip():
        raise HTTPException(400, "Uploaded file is empty")

    try:
        text_content = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = content_bytes.decode("latin-1")

    stripped = text_content.strip()
    if not is_geojson and (stripped.startswith("{") or stripped.startswith("[")):
        is_geojson = True

    agencies_rows = db.execute(
        text("select id, tenant_id, name, short_code from agency")
    ).mappings().all()

    agency_cache: dict[str, dict] = {}
    for a in agencies_rows:
        code = (a["short_code"] or "").strip().upper()
        if user and str(a["tenant_id"]) == str(user.get("tenant_id")):
            agency_cache[code] = dict(a)
        elif code not in agency_cache:
            agency_cache[code] = dict(a)

    has_wards_cache: dict[str, bool] = {}

    def has_city_wards(tenant_id: str) -> bool:
        tid = str(tenant_id)
        if tid not in has_wards_cache:
            res = db.execute(
                text("select 1 from ward where tenant_id=cast(:tenant as uuid) and boundary is not null limit 1"),
                {"tenant": tid},
            ).scalar()
            has_wards_cache[tid] = bool(res)
        return has_wards_cache[tid]

    parsed_rows: list[tuple[dict, dict | None]] = []
    if is_geojson:
        try:
            geo_data = json.loads(text_content)
        except Exception as exc:
            raise HTTPException(400, f"Invalid GeoJSON content: {exc}")

        if isinstance(geo_data, dict):
            if geo_data.get("type") == "FeatureCollection":
                raw_items = geo_data.get("features", [])
            elif geo_data.get("type") == "Feature":
                raw_items = [geo_data]
            elif "features" in geo_data and isinstance(geo_data["features"], list):
                raw_items = geo_data["features"]
            else:
                raw_items = [{"type": "Feature", "geometry": geo_data, "properties": {}}]
        elif isinstance(geo_data, list):
            raw_items = geo_data
        else:
            raise HTTPException(400, "Invalid GeoJSON structure")

        for item in raw_items:
            if not isinstance(item, dict):
                continue
            props = dict(item.get("properties") or {})
            geom = item.get("geometry")
            row_dict = dict(props)
            if geom:
                row_dict["geometry"] = geom
                if isinstance(geom, dict) and geom.get("type") == "LineString":
                    coords = geom.get("coordinates") or []
                    if len(coords) >= 2 and isinstance(coords[0], (list, tuple)) and isinstance(coords[1], (list, tuple)):
                        row_dict.setdefault("lng1", coords[0][0])
                        row_dict.setdefault("lat1", coords[0][1])
                        row_dict.setdefault("lng2", coords[1][0])
                        row_dict.setdefault("lat2", coords[1][1])
            parsed_rows.append((row_dict, geom))
    else:
        reader = csv.DictReader(io.StringIO(text_content))
        if not reader.fieldnames:
            raise HTTPException(400, "CSV file is empty or missing headers")

        for raw_row in reader:
            clean_row = {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in raw_row.items()
                if k is not None
            }
            if not any(v for v in clean_row.values() if v is not None and str(v).strip() != ""):
                continue
            parsed_rows.append((clean_row, None))

    valid = []
    invalid = []

    if not dry_run:
        db.execute(text("create sequence if not exists work_ref_seq"))

    for row_dict, feature_geom in parsed_rows:
        errors = []
        row_data = dict(row_dict)

        # 1. title
        title = (row_data.get("title") or "").strip()
        if not title:
            errors.append("title is required")
        elif len(title) > 300:
            errors.append("title must not exceed 300 characters")

        # 2. category
        cat_raw = (row_data.get("category") or "").strip().lower().replace(" ", "_")
        category = None
        if not cat_raw:
            errors.append("category is required")
        elif cat_raw not in VALID_CATEGORIES:
            errors.append(f"Invalid category '{row_data.get('category')}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}")
        else:
            category = cat_raw

        # 3. agency_code
        agency_code_raw = (row_data.get("agency_code") or row_data.get("agency") or "").strip().upper()
        agency_record = None
        if not agency_code_raw:
            errors.append("agency_code is required")
        elif agency_code_raw not in agency_cache:
            errors.append(f"Agency code '{agency_code_raw}' not found")
        else:
            agency_record = agency_cache[agency_code_raw]

        # 4. planned_start
        planned_start_val = row_data.get("planned_start")
        planned_start_date = None
        if not planned_start_val or str(planned_start_val).strip() == "":
            errors.append("planned_start is required")
        else:
            try:
                planned_start_date = _parse_date(planned_start_val)
            except Exception:
                errors.append(f"Invalid planned_start date '{planned_start_val}', expected YYYY-MM-DD")

        # 5. original_target_end
        target_end_val = row_data.get("original_target_end")
        target_end_date = None
        if not target_end_val or str(target_end_val).strip() == "":
            errors.append("original_target_end is required")
        else:
            try:
                target_end_date = _parse_date(target_end_val)
            except Exception:
                errors.append(f"Invalid original_target_end date '{target_end_val}', expected YYYY-MM-DD")

        if planned_start_date and target_end_date and target_end_date < planned_start_date:
            errors.append("original_target_end cannot be before planned_start")

        # 6. Geometry
        geometry = feature_geom
        if geometry is None:
            lat1 = row_data.get("lat1")
            lng1 = row_data.get("lng1")
            lat2 = row_data.get("lat2")
            lng2 = row_data.get("lng2")
            if (
                lat1 is None or lng1 is None or lat2 is None or lng2 is None
                or str(lat1).strip() == "" or str(lng1).strip() == ""
                or str(lat2).strip() == "" or str(lng2).strip() == ""
            ):
                errors.append("lat1, lng1, lat2, lng2 are all required")
            else:
                try:
                    f_lat1 = float(lat1)
                    f_lng1 = float(lng1)
                    f_lat2 = float(lat2)
                    f_lng2 = float(lng2)
                    if not (-90 <= f_lat1 <= 90 and -90 <= f_lat2 <= 90):
                        errors.append("Latitude values must be between -90 and 90")
                    if not (-180 <= f_lng1 <= 180 and -180 <= f_lng2 <= 180):
                        errors.append("Longitude values must be between -180 and 180")
                    if f_lat1 == f_lat2 and f_lng1 == f_lng2:
                        errors.append("Start and end coordinates must be distinct points")
                    geometry = {
                        "type": "LineString",
                        "coordinates": [[f_lng1, f_lat1], [f_lng2, f_lat2]],
                    }
                except (ValueError, TypeError):
                    errors.append("lat1, lng1, lat2, lng2 must be valid numbers")
        else:
            if not isinstance(geometry, dict) or "type" not in geometry or "coordinates" not in geometry:
                errors.append("geometry must be a valid GeoJSON geometry object")
            elif geometry.get("type") not in ("LineString", "Polygon"):
                errors.append(f"Geometry type '{geometry.get('type')}' is not supported. Must be LineString or Polygon")

        # 7. City boundary & ward validation
        ward_id = None
        if geometry is not None and agency_record is not None:
            tenant_id = agency_record["tenant_id"]
            if has_city_wards(tenant_id):
                if not validate_city_geometry(geometry, tenant_id, db):
                    errors.append("geometry must be a valid LineString or Polygon inside the city")
                else:
                    ward_id = locate_ward(geometry, db, tenant_id)
                    if not ward_id:
                        errors.append("geometry does not intersect a city ward")
            else:
                try:
                    is_valid = db.execute(
                        text("select ST_IsValid(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)) and ST_GeometryType(ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326)) in ('ST_LineString', 'ST_Polygon')"),
                        {"geom": json.dumps(geometry)},
                    ).scalar()
                    if not is_valid:
                        errors.append("geometry is not valid")
                except Exception as e:
                    errors.append(f"Invalid geometry: {e}")

        # 8. User jurisdiction check (if staff)
        if user and agency_record:
            role = user.get("role")
            if role == "junior_engineer" and user.get("ward_id") and ward_id:
                if str(user["ward_id"]) != str(ward_id):
                    errors.append("Outside junior engineer ward jurisdiction")
            if role == "utility_editor" and user.get("agency_id"):
                if str(user["agency_id"]) != str(agency_record["id"]):
                    errors.append("Outside utility editor agency jurisdiction")

        if errors:
            invalid.append({"row": row_data, "errors": errors})
            continue

        # Row is VALID
        if dry_run:
            valid.append(row_data)
        else:
            try:
                with db.begin_nested():
                    seq = db.execute(text("select nextval('work_ref_seq')")).scalar()
                    year = clock.today().year
                    ref_no = f"WRK-{year}-{seq:05d}"
                    tenant_id = agency_record["tenant_id"]
                    actor_id = str(user["id"]) if user and user.get("id") else None
                    length = length_m(geometry, db)

                    work_id = db.execute(
                        text("""
                            insert into work(
                                tenant_id, ref_no, title, purpose, category, status, agency_id,
                                contractor_name, contractor_public, contact_name, contact_phone,
                                contact_email, contact_channel, road_name, ward_id, geometry,
                                length_m, planned_start, original_target_end, current_target_end,
                                disruption_type, disruption_note, is_public, last_update_at, created_by
                            )
                            values(
                                cast(:tenant as uuid), :ref, :title, :purpose, cast(:category as work_category),
                                'planned', cast(:agency as uuid), :contractor, :contractor_public, :contact_name,
                                :contact_phone, :contact_email, :contact_channel, :road, cast(:ward as uuid),
                                ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326), :length, :planned,
                                :original_target, :original_target, cast(:disruption as disruption_type),
                                :disruption_note, :is_public, :now, cast(:actor as uuid)
                            ) returning id
                        """),
                        {
                            "tenant": str(tenant_id),
                            "ref": ref_no,
                            "title": title,
                            "purpose": (row_data.get("purpose") or "").strip() or None,
                            "category": category,
                            "agency": str(agency_record["id"]),
                            "contractor": (row_data.get("contractor_name") or "").strip() or None,
                            "contractor_public": True,
                            "contact_name": (row_data.get("contact_name") or "").strip() or None,
                            "contact_phone": (row_data.get("contact_phone") or "").strip() or None,
                            "contact_email": (row_data.get("contact_email") or "").strip() or None,
                            "contact_channel": (row_data.get("contact_channel") or "").strip() or "office",
                            "road": (row_data.get("road_name") or "").strip() or None,
                            "ward": str(ward_id) if ward_id else None,
                            "geometry": json.dumps(geometry),
                            "length": length,
                            "planned": planned_start_date,
                            "original_target": target_end_date,
                            "disruption": "none",
                            "disruption_note": None,
                            "is_public": True,
                            "now": clock.now(),
                            "actor": actor_id,
                        },
                    ).scalar()

                    emit(
                        db,
                        "WorkCreated.v1",
                        {
                            "tenant_id": str(tenant_id),
                            "work_id": str(work_id),
                            "actor_id": actor_id,
                            "occurred_at": clock.now().isoformat(),
                            "ref_no": ref_no,
                        },
                    )

                    audit_after = {
                        "id": str(work_id),
                        "ref_no": ref_no,
                        "title": title,
                        "agency_id": str(agency_record["id"]),
                        "ward_id": str(ward_id) if ward_id else None,
                    }
                    _write_audit_log(
                        db,
                        tenant_id=tenant_id,
                        actor_id=actor_id,
                        action="created",
                        entity="work",
                        entity_id=str(work_id),
                        after=audit_after,
                    )

                    row_res = dict(row_data)
                    row_res["id"] = str(work_id)
                    row_res["ref_no"] = ref_no
                    valid.append(row_res)
            except Exception as exc:
                invalid.append({"row": row_data, "errors": [f"Database error: {exc}"]})

    if not dry_run and valid:
        db.commit()

    return {"valid": valid, "invalid": invalid}
