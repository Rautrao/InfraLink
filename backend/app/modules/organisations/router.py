from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from app.core.db import get_db
from app.core.security import get_current_user, require_roles

router = APIRouter()
STAFF_ROLES = ("admin", "commissioner", "chief_engineer", "superintending_engineer", "executive_engineer", "assistant_engineer", "junior_engineer", "utility_editor", "contractor", "auditor", "traffic_police")

@router.get("/organisations/ping")
def ping():
    return {"module": "organisations", "status": "ready"}

@router.get("/agencies")
def agencies(db=Depends(get_db)):
    rows = db.execute(text("select id,tenant_id,name,type,short_code from agency order by name")).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "tenant_id": str(r["tenant_id"])} for r in rows]

@router.get("/wards")
def wards(db=Depends(get_db)):
    rows = db.execute(text("select id,tenant_id,zone_id,name,ST_AsGeoJSON(boundary)::json as boundary from ward order by name")).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "tenant_id": str(r["tenant_id"]), "zone_id": str(r["zone_id"]) if r["zone_id"] else None} for r in rows]

@router.get("/zones")
def zones(db=Depends(get_db)):
    rows = db.execute(text("select id,tenant_id,name from zone order by name")).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "tenant_id": str(r["tenant_id"])} for r in rows]

@router.get("/officers")
def officers(ward_id: UUID | None = None, role: str | None = None, db=Depends(get_db), user=Depends(require_roles(*STAFF_ROLES))):
    filters = ["u.active", "u.role <> 'resident'", "(:is_admin or :is_auditor or u.tenant_id=:tenant)"]
    params = {"tenant": user["tenant_id"], "is_admin": user["role"] in ("admin", "commissioner", "chief_engineer"), "is_auditor": user["role"] == "auditor"}
    if ward_id:
        filters.append("u.ward_id=cast(:ward_id as uuid)")
        params["ward_id"] = str(ward_id)
    if role:
        filters.append("u.role=:role")
        params["role"] = role
    rows = db.execute(text(f"""
        select u.id,u.tenant_id,u.agency_id,u.name,u.email,u.role,u.ward_id,u.zone_id,a.name as agency_name
        from app_user u left join agency a on a.id=u.agency_id
        where {' and '.join(filters)}
        order by u.role,u.name
    """), params).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "tenant_id": str(r["tenant_id"]), "agency_id": str(r["agency_id"]) if r["agency_id"] else None, "ward_id": str(r["ward_id"]) if r["ward_id"] else None, "zone_id": str(r["zone_id"]) if r["zone_id"] else None} for r in rows]

@router.get("/escalation-ladder")
def escalation_ladder(db=Depends(get_db)):
    rows = db.execute(text("select id,tenant_id,agency_id,level,role from escalation_level order by tenant_id,agency_id nulls first,level")).mappings().all()
    return [{**dict(r), "id": str(r["id"]), "tenant_id": str(r["tenant_id"]), "agency_id": str(r["agency_id"]) if r["agency_id"] else None} for r in rows]
