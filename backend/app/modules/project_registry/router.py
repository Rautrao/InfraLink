import json
from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from app.core import clock
from app.core.db import get_db
from app.core.events import emit
from app.core.audit import write_audit
from app.core.pagination import paginate
from app.core.security import check_jurisdiction, get_current_user, get_optional_user, require_roles
from app.modules.geo_spatial.service import locate_ward, length_m, validate_city_geometry

router = APIRouter()
WORK_EDIT_ROLES = ("admin", "commissioner", "chief_engineer", "superintending_engineer", "executive_engineer", "assistant_engineer", "junior_engineer", "utility_editor")
DONE_STATES = ("completed", "restoration_verified", "closed")
ACTIVE_UPDATE_STATES = ("ongoing", "permitted", "paused")
WorkCategory = Literal["road_cut","resurfacing","water_pipeline","sewer","drainage","electricity","telecom_duct","gas_pipeline","metro","footpath","other"]
WorkStatus = Literal["planned","permitted","ongoing","paused","completed","restoration_verified","closed"]
Disruption = Literal["none","restricted_access","partial_closure","full_closure"]
TRANSITIONS = {
    "planned": {"permitted", "paused"},
    "permitted": {"ongoing", "paused"},
    "ongoing": {"paused", "completed"},
    "paused": {"ongoing"},
    "completed": {"restoration_verified"},
    "restoration_verified": {"closed"},
    "closed": set(),
}

class WorkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    purpose: str | None = None
    category: WorkCategory
    agency_id: UUID
    geometry: dict
    planned_start: date
    original_target_end: date
    current_target_end: date | None = None
    contractor_name: str | None = None
    contractor_public: bool = True
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_channel: str | None = None
    road_name: str | None = None
    disruption_type: Disruption = "none"
    disruption_note: str | None = None
    is_public: bool = True

class WorkPatch(BaseModel):
    title: str | None = None
    purpose: str | None = None
    category: WorkCategory | None = None
    agency_id: UUID | None = None
    geometry: dict | None = None
    planned_start: date | None = None
    current_target_end: date | None = None
    contractor_name: str | None = None
    contractor_public: bool | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    contact_channel: str | None = None
    road_name: str | None = None
    disruption_type: Disruption | None = None
    disruption_note: str | None = None
    is_public: bool | None = None

class StatusChange(BaseModel):
    to_status: WorkStatus
    reason_code: str | None = None
    explanation: str | None = None

class UpdateCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    pct_complete: int | None = Field(default=None, ge=0, le=100)
    explanation: str | None = None

def _scope_sql(user):
    if not user:
        return [], {}
    role = user["role"]
    if role == "junior_engineer":
        if not user.get("ward_id"):
            return ["false"], {}
        return ["w.ward_id=cast(:scope_ward as uuid)"], {"scope_ward": str(user["ward_id"])}
    if role in ("assistant_engineer", "executive_engineer", "superintending_engineer"):
        if not user.get("zone_id"):
            return ["false"], {}
        return ["wd.zone_id=cast(:scope_zone as uuid)"], {"scope_zone": str(user["zone_id"])}
    if role in ("admin", "commissioner", "chief_engineer", "utility_editor", "auditor"):
        return [], {}
    # The scaffold schema has no work assignment table yet; contractor scope
    # cannot safely be inferred, so contractor data is not expanded here.
    return ["false"], {}

def _work_row(db, work_id, user):
    sql = """select w.*, ST_AsGeoJSON(w.geometry)::json as geometry_json,
        a.name as agency_name, wd.name as ward_name, wd.zone_id as ward_zone_id,
        coalesce(cc.overdue_days,7) as overdue_days,
        (w.current_target_end < :today and w.status::text not in ('completed','restoration_verified','closed')) as delayed,
        (w.status::text in ('ongoing','permitted','paused') and (w.last_update_at is null or w.last_update_at < :now - make_interval(days=>coalesce(cc.overdue_days,7)))) as update_overdue
        from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id
        left join city_config cc on cc.tenant_id=w.tenant_id
        where w.id=cast(:id as uuid)"""
    params = {"id": str(work_id), "today": clock.today(), "now": clock.now()}
    scope, scope_params = _scope_sql(user)
    params.update(scope_params)
    if user:
        if user["role"] not in ("admin", "commissioner", "chief_engineer", "auditor", "utility_editor"):
            sql += " and " + " and ".join(scope)
        sql += " and w.tenant_id=cast(:tenant as uuid)"
        params["tenant"] = str(user["tenant_id"])
    else:
        sql += " and w.is_public"
    row = db.execute(text(sql), params).mappings().first()
    if not row:
        raise HTTPException(404, "Work not found")
    return row

def _derived(row):
    if "delayed" in row and "update_overdue" in row:
        return bool(row["delayed"]), bool(row["update_overdue"])
    today = clock.today()
    delayed = bool(row["current_target_end"] and row["current_target_end"] < today and row["status"] not in DONE_STATES)
    update_overdue = bool(row["status"] in ACTIVE_UPDATE_STATES and (row["last_update_at"] is None or (clock.now() - row["last_update_at"]).total_seconds() > row["overdue_days"] * 86400))
    return delayed, update_overdue

def _mask_phone(phone):
    if not phone: return None
    visible = str(phone)[-4:]
    return "*" * max(0, len(str(phone)) - 4) + visible

def _list_item(row, user):
    delayed, update_overdue = _derived(row)
    return {"id": str(row["id"]), "ref_no": row["ref_no"], "title": row["title"], "purpose": row["purpose"], "category": row["category"], "status": row["status"], "delayed": delayed, "update_overdue": update_overdue, "agency": {"id": str(row["agency_id"]), "name": row["agency_name"]}, "road_name": row["road_name"], "ward": {"id": str(row["ward_id"]), "name": row["ward_name"]} if row["ward_id"] else None, "geometry": row["geometry_json"], "planned_start": row["planned_start"], "original_target_end": row["original_target_end"], "current_target_end": row["current_target_end"], "pct_complete": row["pct_complete"], "disruption": {"type": row["disruption_type"], "note": row["disruption_note"]}, "last_update_at": row["last_update_at"]}

def _detail(db, row, user):
    wid = str(row["id"])
    delayed, update_overdue = _derived(row)
    revisions = db.execute(text("select old_target,new_target,reason_code,explanation,at from work_date_revision where work_id=cast(:id as uuid) order by at"), {"id": wid}).mappings().all()
    milestones = db.execute(text("select id,name,planned_date,actual_date,pct,sort from work_milestone where work_id=cast(:id as uuid) order by sort,planned_date"), {"id": wid}).mappings().all()
    updates = db.execute(text("select text,pct_complete,at,is_public from work_update where work_id=cast(:id as uuid) and (:staff or is_public) order by at desc"), {"id": wid, "staff": bool(user)}).mappings().all()
    evidence = db.execute(text("select public_path,taken_at,kind from evidence where work_id=cast(:id as uuid) and public_path is not null order by taken_at desc"), {"id": wid}).mappings().all()
    permits = db.execute(text("select type,status,valid_from,valid_to from permit where work_id=cast(:id as uuid) order by applied_at desc"), {"id": wid}).mappings().all()
    votes = db.execute(text("select count(*) filter(where kind='still_ongoing_yes') as yes,count(*) filter(where kind='still_ongoing_no') as no,max(created_at) as last_confirmed_at from feedback_ticket where work_id=cast(:id as uuid) and kind in ('still_ongoing_yes','still_ongoing_no')"), {"id": wid}).mappings().first()
    contact_phone = row["contact_phone"] if user or row["contact_channel"] == "official" else _mask_phone(row["contact_phone"])
    contractor = row["contractor_name"] if user or row["contractor_public"] else None
    return {
        "id": wid, "ref_no": row["ref_no"], "title": row["title"], "purpose": row["purpose"], "category": row["category"], "status": row["status"], "delayed": delayed, "update_overdue": update_overdue,
        "agency": {"id": str(row["agency_id"]), "name": row["agency_name"]}, "contractor_name": contractor,
        "contact": {"name": row["contact_name"], "phone_masked": contact_phone, "email": row["contact_email"], "channel": row["contact_channel"]},
        "road_name": row["road_name"], "ward": {"id": str(row["ward_id"]), "name": row["ward_name"]} if row["ward_id"] else None,
        "geometry": row["geometry_json"], "length_m": row["length_m"], "planned_start": row["planned_start"], "original_target_end": row["original_target_end"], "current_target_end": row["current_target_end"],
        "date_revisions": [{"old":x["old_target"],"new":x["new_target"],"reason_code":x["reason_code"],"explanation":x["explanation"],"at":x["at"]} for x in revisions], "pct_complete": row["pct_complete"], "milestones": [dict(x) for x in milestones],
        "disruption": {"type": row["disruption_type"], "note": row["disruption_note"]}, "last_update_at": row["last_update_at"],
        "updates": [{"text": x["text"], "pct_complete": x["pct_complete"], "at": x["at"]} for x in updates],
        "evidence": [{"public_url": x["public_path"], "taken_at": x["taken_at"], "kind": x["kind"]} for x in evidence],
        "permits": [dict(x) for x in permits], "nearby_notices": [],
        "still_ongoing": {"yes": votes["yes"], "no": votes["no"], "last_confirmed_at": votes["last_confirmed_at"]},
    }

def _filters(user, bbox, ward_id, road, category, agency_id, status, delayed, q):
    clauses, params = [], {"today": clock.today(), "now": clock.now()}
    if not user: clauses.append("w.is_public")
    else:
        clauses.append("w.tenant_id=cast(:tenant as uuid)")
        params["tenant"] = str(user["tenant_id"])
        scope, scope_params = _scope_sql(user)
        clauses.extend(scope)
        params.update(scope_params)
    if ward_id:
        clauses.append("w.ward_id=cast(:ward_id as uuid)"); params["ward_id"] = ward_id
    if road:
        clauses.append("w.road_name ilike :road"); params["road"] = f"%{road}%"
    if category:
        clauses.append("w.category=cast(:category as work_category)"); params["category"] = category
    if agency_id:
        clauses.append("w.agency_id=cast(:agency_id as uuid)"); params["agency_id"] = agency_id
    if status:
        clauses.append("w.status=cast(:status as work_status)"); params["status"] = status
    if delayed is not None:
        delayed_sql = "(w.current_target_end < :today and w.status::text not in ('completed','restoration_verified','closed'))"
        clauses.append(delayed_sql if delayed else f"not {delayed_sql}")
    if q:
        clauses.append("(w.title ilike :q or coalesce(w.purpose,'') ilike :q or coalesce(w.road_name,'') ilike :q)")
        params["q"] = f"%{q}%"
    if bbox:
        try:
            west, south, east, north = (float(x.strip()) for x in bbox.split(","))
            if west >= east or south >= north: raise ValueError()
        except ValueError:
            raise HTTPException(422, "bbox must be west,south,east,north")
        clauses.append("ST_Intersects(w.geometry,ST_MakeEnvelope(:west,:south,:east,:north,4326))")
        params.update({"west": west, "south": south, "east": east, "north": north})
    return clauses, params

@router.get("/project_registry/ping")
def ping(): return {"module": "project_registry", "status": "ready"}

@router.get("/works")
def list_works(bbox: str | None = None, ward_id: UUID | None = None, road: str | None = None, category: WorkCategory | None = None, agency_id: UUID | None = None, status: WorkStatus | None = None, delayed: bool | None = None, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db=Depends(get_db), user=Depends(get_optional_user)):
    clauses, params = _filters(user, bbox, ward_id, road, category, agency_id, status, delayed, q)
    condition = " and ".join(clauses) or "true"
    total = db.execute(text(f"select count(*) from work w left join ward wd on wd.id=w.ward_id where {condition}"), params).scalar() or 0
    overdue = "coalesce(cc.overdue_days,7)"
    rows = db.execute(text(f"""
        select w.*,ST_AsGeoJSON(w.geometry)::json as geometry_json,a.name as agency_name,wd.name as ward_name,wd.zone_id as ward_zone_id,{overdue} as overdue_days,
          (w.current_target_end < :today and w.status::text not in ('completed','restoration_verified','closed')) as delayed,
          (w.status::text in ('ongoing','permitted','paused') and (w.last_update_at is null or w.last_update_at < :now - make_interval(days=>{overdue}))) as update_overdue
        from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id left join city_config cc on cc.tenant_id=w.tenant_id
        where {condition} order by w.planned_start nulls last,w.ref_no
        limit :limit offset :offset
    """), {**params, "limit": page_size, "offset": (page - 1) * page_size}).mappings().all()
    return {"items": [_list_item(row, user) for row in rows], "total": total, "page": page, "page_size": page_size}

@router.get("/works/geojson")
def works_geojson(bbox: str | None = None, ward_id: UUID | None = None, road: str | None = None, category: WorkCategory | None = None, agency_id: UUID | None = None, status: WorkStatus | None = None, delayed: bool | None = None, q: str | None = None, db=Depends(get_db), user=Depends(get_optional_user)):
    clauses, params = _filters(user, bbox, ward_id, road, category, agency_id, status, delayed, q)
    condition = " and ".join(clauses) or "true"
    rows = db.execute(text(f"""
        select w.id,w.ref_no,w.title,w.status,w.category,w.planned_start,w.current_target_end,w.last_update_at,w.geometry,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(w.geometry,0.00002))::json as simplified,
               a.name as agency_name,coalesce(cc.overdue_days,7) as overdue_days,
               (w.current_target_end < :today and w.status::text not in ('completed','restoration_verified','closed')) as delayed
        from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id left join city_config cc on cc.tenant_id=w.tenant_id
        where {condition} order by w.ref_no
    """), params).mappings().all()
    features = []
    for r in rows:
        delayed_flag = bool(r["delayed"])
        features.append({"type":"Feature","id":str(r["id"]),"geometry":r["simplified"],"properties":{"id":str(r["id"]),"ref_no":r["ref_no"],"title":r["title"],"status":r["status"],"delayed":delayed_flag,"category":r["category"],"agency":r["agency_name"],"last_update_at":r["last_update_at"]}})
    return {"type":"FeatureCollection","features":features}

@router.get("/works/{work_id}")
def get_work(work_id: UUID, db=Depends(get_db), user=Depends(get_optional_user)):
    row = _work_row(db, work_id, user)
    return _detail(db, row, user)

@router.post("/works", status_code=201)
def create_work(body: WorkCreate, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    if body.current_target_end and body.current_target_end != body.original_target_end:
        raise HTTPException(422, "original_target_end and current_target_end must match when creating a work")
    check_jurisdiction(user, agency_id=body.agency_id)
    if not validate_city_geometry(body.geometry,user["tenant_id"],db): raise HTTPException(422, "geometry must be a valid LineString or Polygon inside the city")
    ward_id = locate_ward(body.geometry, db, user["tenant_id"])
    if not ward_id: raise HTTPException(422, "geometry does not intersect a city ward")
    check_jurisdiction(user, ward_id=ward_id, agency_id=body.agency_id)
    # Sequence is also created idempotently here for databases initialized before this endpoint landed.
    db.execute(text("create sequence if not exists work_ref_seq"))
    seq = db.execute(text("select nextval('work_ref_seq')")).scalar()
    year = clock.today().year
    ref_no = f"WRK-{year}-{seq:05d}"
    work_id = db.execute(text("""
        insert into work(tenant_id,ref_no,title,purpose,category,status,agency_id,contractor_name,contractor_public,contact_name,contact_phone,contact_email,contact_channel,road_name,ward_id,geometry,length_m,planned_start,original_target_end,current_target_end,disruption_type,disruption_note,is_public,last_update_at,created_by)
        values(cast(:tenant as uuid),:ref,:title,:purpose,cast(:category as work_category),'planned',cast(:agency as uuid),:contractor,:contractor_public,:contact_name,:contact_phone,:contact_email,:contact_channel,:road,cast(:ward as uuid),ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326),:length,:planned,:original_target,:original_target,cast(:disruption as disruption_type),:disruption_note,:is_public,:now,cast(:actor as uuid)) returning id
    """), {"tenant":str(user["tenant_id"]),"ref":ref_no,"title":body.title,"purpose":body.purpose,"category":body.category,"agency":str(body.agency_id),"contractor":body.contractor_name,"contractor_public":body.contractor_public,"contact_name":body.contact_name,"contact_phone":body.contact_phone,"contact_email":body.contact_email,"contact_channel":body.contact_channel,"road":body.road_name,"ward":str(ward_id),"geometry":json.dumps(body.geometry),"length":length_m(body.geometry,db),"planned":body.planned_start,"original_target":body.original_target_end,"disruption":body.disruption_type,"disruption_note":body.disruption_note,"is_public":body.is_public,"now":clock.now(),"actor":str(user["id"])}).scalar()
    new = {"id": str(work_id), "ref_no": ref_no, "title": body.title, "agency_id": str(body.agency_id), "ward_id": str(ward_id)}
    emit(db, "WorkCreated.v1", {"tenant_id":str(user["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"ref_no":ref_no})
    write_audit(db, user, "created", "work", work_id, after=new)
    db.commit()
    return _detail(db, _work_row(db, work_id, user), user)

@router.patch("/works/{work_id}")
def patch_work(work_id: UUID, body: WorkPatch, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    row = _work_row(db, work_id, user)
    if "current_target_end" in body.model_fields_set:
        raise HTTPException(422, "use /works/{id}/dates")
    check_jurisdiction(user, row["ward_id"], row["agency_id"])
    changes = body.model_dump(exclude_unset=True)
    if not changes: return _detail(db, row, user)
    before = {k: row[k] for k in changes if k in row}
    geometry_value = changes.pop("geometry", None)
    if "agency_id" in changes:
        check_jurisdiction(user, row["ward_id"], changes["agency_id"])
    assignments=[]; params={"id":str(work_id),"updated_at":clock.now()}
    for key,value in changes.items():
        if key == "agency_id": value = str(value); expression=f"cast(:{key} as uuid)"
        elif key == "category": expression=f"cast(:{key} as work_category)"
        elif key == "disruption_type": expression=f"cast(:{key} as disruption_type)"
        else: expression=f":{key}"
        assignments.append(f"{key}={expression}"); params[key]=value
    if geometry_value is not None:
        if not validate_city_geometry(geometry_value,user["tenant_id"],db): raise HTTPException(422,"geometry must be valid and inside the city")
        new_ward=locate_ward(geometry_value,db,user["tenant_id"])
        assignments.extend(["geometry=ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)","length_m=:length_m","ward_id=cast(:ward_id as uuid)"])
        params.update({"geometry":json.dumps(geometry_value),"length_m":length_m(geometry_value,db),"ward_id":str(new_ward)})
    assignments.append("updated_at=:updated_at")
    db.execute(text(f"update work set {','.join(assignments)} where id=cast(:id as uuid)"),params)
    changed_fields=list(changes)+(["geometry"] if geometry_value is not None else [])
    after={**before,**changes}
    emit(db,"WorkUpdated.v1",{"tenant_id":str(row["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"changed_fields":changed_fields})
    if row["disruption_type"] not in ("partial_closure","full_closure") and changes.get("disruption_type") in ("partial_closure","full_closure"):
        emit(db,"ClosureAdded.v1",{"tenant_id":str(row["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"disruption_type":changes["disruption_type"]})
    write_audit(db,user,"updated","work",work_id,before=before,after=after)
    db.commit()
    return _detail(db,_work_row(db,work_id,user),user)

@router.post("/works/{work_id}/status")
def change_status(work_id: UUID, body: StatusChange, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    row=_work_row(db,work_id,user); check_jurisdiction(user,row["ward_id"],row["agency_id"])
    to_status=body.to_status
    if to_status not in TRANSITIONS: raise HTTPException(422,"Unknown work status")
    if to_status not in TRANSITIONS[row["status"]]: raise HTTPException(409,f"Invalid status transition: {row['status']} -> {to_status}")
    if to_status=="paused" and (not body.reason_code or not body.explanation): raise HTTPException(422,"Pausing requires reason_code and explanation")
    if to_status=="completed" and row["pct_complete"] != 100: raise HTTPException(409,"Work can be completed only at 100 percent")
    if to_status=="restoration_verified":
        # TODO(Aayushya): replace this scaffold stub with evidence.has_restoration_evidence(work_id).
        from app.modules.evidence.service import has_restoration_evidence
        if not has_restoration_evidence(work_id,db): raise HTTPException(409,"Restoration evidence is required")
    db.execute(text("update work set status=cast(:status as work_status),updated_at=:at, restoration_verified_at=case when :status='restoration_verified' then :at else restoration_verified_at end where id=cast(:id as uuid)"),{"status":to_status,"at":clock.now(),"id":str(work_id)})
    db.execute(text("insert into work_status_history(tenant_id,work_id,from_status,to_status,reason_code,explanation,by_user,at) values(cast(:tenant as uuid),cast(:id as uuid),cast(:from_status as work_status),cast(:to_status as work_status),:reason,:explanation,cast(:actor as uuid),:at)"),{"tenant":str(row["tenant_id"]),"id":str(work_id),"from_status":row["status"],"to_status":to_status,"reason":body.reason_code,"explanation":body.explanation,"actor":str(user["id"]),"at":clock.now()})
    emit(db,"WorkStatusChanged.v1",{"tenant_id":str(row["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"from_status":row["status"],"to_status":to_status,"reason_code":body.reason_code})
    if to_status=="restoration_verified": emit(db,"RestorationVerified.v1",{"tenant_id":str(row["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat()})
    write_audit(db,user,"status_changed","work",work_id,before={"status":row["status"]},after={"status":to_status,"reason_code":body.reason_code,"explanation":body.explanation})
    db.commit()
    return _detail(db,_work_row(db,work_id,user),user)

@router.post("/works/{work_id}/updates",status_code=201)
def add_update(work_id: UUID, body: UpdateCreate, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    row=_work_row(db,work_id,user); check_jurisdiction(user,row["ward_id"],row["agency_id"])
    if body.pct_complete is not None and body.pct_complete < row["pct_complete"] and not body.explanation:
        raise HTTPException(422,"Reducing completion requires an explanation")
    db.execute(text("insert into work_update(tenant_id,work_id,text,pct_complete,by_user,at,is_public) values(cast(:tenant as uuid),cast(:id as uuid),:text,:pct,cast(:actor as uuid),:at,true)"),{"tenant":str(row["tenant_id"]),"id":str(work_id),"text":body.text,"pct":body.pct_complete,"actor":str(user["id"]),"at":clock.now()})
    db.execute(text("update work set last_update_at=:at,updated_at=:at,pct_complete=coalesce(:pct,pct_complete) where id=cast(:id as uuid)"),{"at":clock.now(),"pct":body.pct_complete,"id":str(work_id)})
    emit(db,"WorkUpdated.v1",{"tenant_id":str(row["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"changed_fields":["last_update_at","pct_complete"] if body.pct_complete is not None else ["last_update_at"]})
    write_audit(db,user,"progress_update","work",work_id,after={"text":body.text,"pct_complete":body.pct_complete,"explanation":body.explanation})
    db.commit()
    return {"status":"ok","last_update_at":clock.now(),"pct_complete":body.pct_complete if body.pct_complete is not None else row["pct_complete"]}

@router.get("/works/{work_id}/history")
def work_history(work_id: UUID, db=Depends(get_db), user=Depends(get_optional_user)):
    row=_work_row(db,work_id,user); wid=str(work_id)
    history=[]
    sources=[
        ("status", "select 'status' as kind,from_status,to_status as value,reason_code,explanation,at from work_status_history where work_id=cast(:id as uuid)"),
        ("date_revision", "select 'date_revision' as kind,old_target::text as from_status,new_target::text as value,reason_code,explanation,at from work_date_revision where work_id=cast(:id as uuid)"),
        ("update", "select 'update' as kind,null::text as from_status,text as value,null::text as reason_code,null::text as explanation,at from work_update where work_id=cast(:id as uuid) and (:staff or is_public)"),
        ("evidence", "select 'evidence' as kind,null::text as from_status,kind::text as value,null::text as reason_code,public_path as explanation,taken_at as at from evidence where work_id=cast(:id as uuid) and public_path is not null"),
        ("decision", "select 'decision' as kind,null::text as from_status,'nearby work coordinated' as value,null::text as reason_code,null::text as explanation,d.at from conflict_decision d join conflict_alert c on c.id=d.alert_id where (:work= c.work_a or :work= c.work_b) and d.action in ('coordinate_dates','combine_work','reschedule')"),
    ]
    for _,sql in sources:
        params={"id":wid,"staff":bool(user),"work":work_id}
        rows=db.execute(text(sql),params).mappings().all()
        history.extend(dict(r) for r in rows)
    history.sort(key=lambda x:x.get("at") or clock.now())
    return {"work_id":wid,"items":history}
