from collections.abc import Mapping
from uuid import UUID
from sqlalchemy import text
from app.core.db import SessionLocal

def get_assignee(work, level: int, session=None):
    """Find the officer at level (1=JE), falling upward if that slot is vacant.

    Callers may pass their transaction session. If omitted, this function owns a
    short-lived session. `work` may be a mapping containing id/tenant_id/ward_id/
    agency_id or a work UUID (the latter is loaded here).
    """
    owns_session = session is None
    db = session or SessionLocal()
    try:
        if isinstance(work, Mapping):
            work_row=work
        elif hasattr(work,"tenant_id") and hasattr(work,"id"):
            work_row={"id":work.id,"tenant_id":work.tenant_id,"ward_id":getattr(work,"ward_id",None),"agency_id":getattr(work,"agency_id",None)}
        else:
            work_row = db.execute(text("select id,tenant_id,ward_id,agency_id from work where id=:id"), {"id": work}).mappings().first()
        if not work_row:
            return None
        tenant_id = work_row["tenant_id"]
        ward_id = work_row.get("ward_id") if hasattr(work_row, "get") else work_row["ward_id"]
        agency_id = work_row.get("agency_id") if hasattr(work_row, "get") else work_row["agency_id"]
        zone_id = db.execute(text("select zone_id from ward where id=:ward"), {"ward": ward_id}).scalar() if ward_id else None
        ladder = db.execute(text("""
            select level,role from escalation_level
            where tenant_id=:tenant and level >= :level and (agency_id=:agency or agency_id is null)
            order by level, (agency_id is null)
        """), {"tenant": tenant_id, "level": level, "agency": agency_id}).mappings().all()
        for rung in ladder:
            candidate = db.execute(text("""
                select id,tenant_id,agency_id,name,email,phone,role,ward_id,zone_id
                from app_user where tenant_id=:tenant and role=:role and active
                  and (agency_id=:agency or agency_id is null)
                  and (ward_id=:ward or ward_id is null)
                  and (zone_id=:zone or zone_id is null)
                order by (ward_id is not null) desc,(zone_id is not null) desc,(agency_id is not null) desc
                limit 1
            """), {"tenant": tenant_id, "role": rung["role"], "agency": agency_id, "ward": ward_id, "zone": zone_id}).mappings().first()
            if candidate:
                return dict(candidate)
        return None
    finally:
        if owns_session:
            db.close()
