from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy import text
from app.core import clock
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.events import emit
from app.core.events import subscribe
from app.core.security import check_jurisdiction,require_roles

router=APIRouter()
STAFF=("admin","commissioner","chief_engineer","superintending_engineer","executive_engineer","assistant_engineer","junior_engineer","utility_editor","auditor")
class DecisionDates(BaseModel):
    planned_start:date|None=None
    current_target_end:date|None=None

class DecisionBody(BaseModel):
    action:Literal["coordinate_dates","combine_work","reschedule","justify_both"]
    note:str=Field(min_length=15,max_length=2000)
    work_id:UUID|None=None
    new_dates:DecisionDates|None=None
    reason_code:str|None=None

def _scope(user,alias="w"):
    if user["role"] in ("admin","commissioner","chief_engineer","auditor"):return "true",{}
    if user["role"]=="junior_engineer":return (f"{alias}.ward_id=cast(:ward as uuid)",{"ward":str(user["ward_id"])} ) if user.get("ward_id") else ("false",{})
    if user["role"] in ("assistant_engineer","executive_engineer","superintending_engineer"):return ("wd.zone_id=cast(:zone as uuid)",{"zone":str(user["zone_id"])} ) if user.get("zone_id") else ("false",{})
    if user["role"]=="utility_editor":return (f"{alias}.agency_id=cast(:agency as uuid)",{"agency":str(user["agency_id"])} ) if user.get("agency_id") else ("false",{})
    return "false",{}

def _conflict_scope(user):
    if user["role"] in ("admin","commissioner","chief_engineer","auditor"):return "true",{}
    if user["role"]=="junior_engineer":return ("(a.ward_id=cast(:ward as uuid) or b.ward_id=cast(:ward as uuid))",{"ward":str(user["ward_id"])} ) if user.get("ward_id") else ("false",{})
    if user["role"] in ("assistant_engineer","executive_engineer","superintending_engineer"):return ("(wda.zone_id=cast(:zone as uuid) or wdb.zone_id=cast(:zone as uuid))",{"zone":str(user["zone_id"])} ) if user.get("zone_id") else ("false",{})
    if user["role"]=="utility_editor":return ("(a.agency_id=cast(:agency as uuid) or b.agency_id=cast(:agency as uuid))",{"agency":str(user["agency_id"])} ) if user.get("agency_id") else ("false",{})
    return "false",{}

def _check_alert_scope(db,user,alert_id):
    scope,params=_conflict_scope(user)
    ok=db.execute(text(f"select 1 from conflict_alert c join work a on a.id=c.work_a join work b on b.id=c.work_b left join ward wda on wda.id=a.ward_id left join ward wdb on wdb.id=b.ward_id where c.id=cast(:id as uuid) and c.tenant_id=cast(:tenant as uuid) and {scope}"),{"id":str(alert_id),"tenant":str(user["tenant_id"]),**params}).scalar()
    if not ok:raise HTTPException(403,"Outside conflict jurisdiction")

@router.get("/conflicts/ping")
def ping():return {"module":"conflict_engine","status":"ready"}

def scan_conflicts(db,tenant_id,work_id=None,detected_by="submission"):
    config=db.execute(text("select coalesce(buffer_m,15) buffer_m,coalesce(lookback_months,24) lookback_months from city_config where tenant_id=cast(:tenant as uuid)"),{"tenant":str(tenant_id)}).mappings().first() or {"buffer_m":15,"lookback_months":24}
    params={"tenant":str(tenant_id),"buffer":float(config["buffer_m"]),"months":int(config["lookback_months"]),"work":str(work_id) if work_id else None}
    pairs=db.execute(text("""
      select a.id work_a,b.id work_b,'overlap'::conflict_type kind,
        (least(a.current_target_end,b.current_target_end)-greatest(a.planned_start,b.planned_start)+1) overlap_days,
        null::int days_since_resurfacing,ST_Distance(ST_Transform(a.geometry,32643),ST_Transform(b.geometry,32643)) distance_m
      from work a join work b on a.tenant_id=b.tenant_id and a.id<b.id
      where a.tenant_id=cast(:tenant as uuid) and a.geometry is not null and b.geometry is not null
        and a.planned_start is not null and b.planned_start is not null
        and a.current_target_end is not null and b.current_target_end is not null
        and daterange(a.planned_start,a.current_target_end,'[]') && daterange(b.planned_start,b.current_target_end,'[]')
        and ST_Intersects(ST_Buffer(ST_Transform(a.geometry,32643),:buffer),ST_Buffer(ST_Transform(b.geometry,32643),:buffer))
        and (cast(:work as uuid) is null or a.id=cast(:work as uuid) or b.id=cast(:work as uuid))
      union all
      select old.id,new.id,'recent_resurfacing'::conflict_type,null::int,
        (new.planned_start-coalesce(old.resurfaced_on,old.actual_end))::int,
        ST_Distance(ST_Transform(old.geometry,32643),ST_Transform(new.geometry,32643))
      from work old join work new on old.tenant_id=new.tenant_id and old.id<>new.id
      where old.tenant_id=cast(:tenant as uuid) and old.geometry is not null and new.geometry is not null
        and new.planned_start is not null and old.status::text in ('completed','restoration_verified')
        and (old.category::text='resurfacing' or old.resurfaced_on is not null)
        and coalesce(old.resurfaced_on,old.actual_end) between new.planned_start-make_interval(months=>:months) and new.planned_start
        and ST_Intersects(ST_Buffer(ST_Transform(old.geometry,32643),:buffer),ST_Buffer(ST_Transform(new.geometry,32643),:buffer))
        and (cast(:work as uuid) is null or old.id=cast(:work as uuid) or new.id=cast(:work as uuid))
    """),params).mappings().all()
    inserted=0
    for pair in pairs:
        a,b=pair["work_a"],pair["work_b"]
        exists=db.execute(text("select c.id from conflict_alert c join work wa on wa.id=c.work_a join work wb on wb.id=c.work_b left join lateral (select max(at) resolved_at from conflict_decision where alert_id=c.id) d on true where c.tenant_id=cast(:tenant as uuid) and c.work_a=cast(:a as uuid) and c.work_b=cast(:b as uuid) and c.type=cast(:type as conflict_type) and (c.status='open' or (c.status='resolved' and greatest(wa.updated_at,wb.updated_at)<=coalesce(d.resolved_at,c.detected_at))) order by (c.status='open') desc,c.detected_at desc limit 1"),{"tenant":str(tenant_id),"a":str(a),"b":str(b),"type":pair["kind"]}).scalar()
        if exists:continue
        alert=db.execute(text("insert into conflict_alert(tenant_id,work_a,work_b,type,overlap_days,days_since_resurfacing,distance_m,detected_at,detected_by) values(cast(:tenant as uuid),cast(:a as uuid),cast(:b as uuid),cast(:type as conflict_type),:days,:since,:distance,:at,cast(:detected_by as conflict_detected_by)) returning id"),{"tenant":str(tenant_id),"a":str(a),"b":str(b),"type":pair["kind"],"days":pair["overlap_days"],"since":pair["days_since_resurfacing"],"distance":pair["distance_m"],"at":clock.now(),"detected_by":detected_by}).scalar()
        emit(db,"ConflictDetected.v1",{"tenant_id":str(tenant_id),"work_id":str(b),"conflict_id":str(alert),"occurred_at":clock.now().isoformat(),"type":pair["kind"]})
        inserted+=1
    return inserted

def scan_all_conflicts():
    from app.core.db import SessionLocal
    with SessionLocal() as db:
        tenants=db.execute(text("select id from tenant")).scalars().all();count=sum(scan_conflicts(db,t,detected_by="nightly_scan") for t in tenants);db.commit();return count

def _scan_subscriber(event):
    tenant=event.get("tenant_id");work=event.get("work_id")
    if not tenant or not work:return
    from app.core.db import SessionLocal
    with SessionLocal() as db:
        scan_conflicts(db,tenant,work);db.commit()

for _event in ("WorkCreated.v1","WorkUpdated.v1","PermitSubmitted.v1"):
    subscribe(_event)(_scan_subscriber)

@router.post("/conflicts/scan")
def scan_endpoint(db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    total=scan_conflicts(db,user["tenant_id"]);db.commit();return {"created":total}

@router.get("/conflicts")
def list_conflicts(status:str="open",ward_id:UUID|None=None,db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    if status not in ("open","resolved"):raise HTTPException(422,"status must be open or resolved")
    scope,params=_conflict_scope(user);params.update({"tenant":str(user["tenant_id"]),"status":status})
    cond=["c.tenant_id=cast(:tenant as uuid)","c.status::text=:status",scope]
    if ward_id:cond.append("(a.ward_id=cast(:ward_filter as uuid) or b.ward_id=cast(:ward_filter as uuid))");params["ward_filter"]=str(ward_id)
    rows=db.execute(text(f"select c.id,c.type::text type,c.status::text status,c.overlap_days,c.days_since_resurfacing,c.distance_m,c.detected_at,a.id a_id,a.ref_no a_ref,a.title a_title,a.road_name a_road,a.planned_start a_start,a.current_target_end a_end,aa.name a_agency,b.id b_id,b.ref_no b_ref,b.title b_title,b.road_name b_road,b.planned_start b_start,b.current_target_end b_end,ab.name b_agency from conflict_alert c join work a on a.id=c.work_a join work b on b.id=c.work_b join agency aa on aa.id=a.agency_id join agency ab on ab.id=b.agency_id left join ward wda on wda.id=a.ward_id left join ward wdb on wdb.id=b.ward_id where {' and '.join(cond)} order by c.detected_at desc"),params).mappings().all()
    return {"items":[{"id":str(r["id"]),"type":r["type"],"status":r["status"],"overlap_days":r["overlap_days"],"days_since_resurfacing":r["days_since_resurfacing"],"distance_m":float(r["distance_m"]) if r["distance_m"] is not None else None,"detected_at":r["detected_at"],"work_a":{"id":str(r["a_id"]),"ref_no":r["a_ref"],"title":r["a_title"],"road_name":r["a_road"],"planned_start":r["a_start"],"current_target_end":r["a_end"],"agency":{"name":r["a_agency"]}},"work_b":{"id":str(r["b_id"]),"ref_no":r["b_ref"],"title":r["b_title"],"road_name":r["b_road"],"planned_start":r["b_start"],"current_target_end":r["b_end"],"agency":{"name":r["b_agency"]}}} for r in rows]}

@router.get("/conflicts/{alert_id}")
def conflict_detail(alert_id:UUID,db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    row=db.execute(text("select c.*,c.type::text type,c.status::text status,greatest(a.planned_start,b.planned_start) overlap_start,least(a.current_target_end,b.current_target_end) overlap_end,a.id a_id,a.ref_no a_ref,a.title a_title,a.purpose a_purpose,a.road_name a_road,a.ward_id a_ward,a.agency_id a_agency,a.planned_start a_start,a.current_target_end a_end,a.contact_name a_contact,a.contact_phone a_phone,a.contact_email a_email,ST_AsGeoJSON(a.geometry)::json a_geom,ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform(a.geometry,32643),coalesce(ca.buffer_m,15)),4326))::json a_buffer,aa.name a_agency_name,b.id b_id,b.ref_no b_ref,b.title b_title,b.purpose b_purpose,b.road_name b_road,b.ward_id b_ward,b.agency_id b_agency,b.planned_start b_start,b.current_target_end b_end,b.contact_name b_contact,b.contact_phone b_phone,b.contact_email b_email,ST_AsGeoJSON(b.geometry)::json b_geom,ST_AsGeoJSON(ST_Transform(ST_Buffer(ST_Transform(b.geometry,32643),coalesce(ca.buffer_m,15)),4326))::json b_buffer,ab.name b_agency_name,wd.name ward_name from conflict_alert c join work a on a.id=c.work_a join work b on b.id=c.work_b join agency aa on aa.id=a.agency_id join agency ab on ab.id=b.agency_id left join ward wd on wd.id=a.ward_id left join city_config ca on ca.tenant_id=c.tenant_id where c.id=cast(:id as uuid) and c.tenant_id=cast(:tenant as uuid)"),{"id":str(alert_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row:raise HTTPException(404,"Conflict not found")
    _check_alert_scope(db,user,alert_id)
    history=db.execute(text("select d.action::text action,d.note,d.at,u.name from conflict_decision d left join app_user u on u.id=d.decided_by where d.alert_id=cast(:id as uuid) order by d.at"),{"id":str(alert_id)}).mappings().all()
    def work(prefix):return {"id":str(row[f"{prefix}_id"]),"ref_no":row[f"{prefix}_ref"],"title":row[f"{prefix}_title"],"purpose":row[f"{prefix}_purpose"],"road_name":row[f"{prefix}_road"],"ward":{"name":row["ward_name"]} if prefix=="a" else None,"agency":{"name":row[f"{prefix}_agency_name"]},"planned_start":row[f"{prefix}_start"],"current_target_end":row[f"{prefix}_end"],"contact":{"name":row[f"{prefix}_contact"],"phone_masked":row[f"{prefix}_phone"],"email":row[f"{prefix}_email"]},"geometry":row[f"{prefix}_geom"]}
    return {"id":str(alert_id),"type":row["type"],"status":row["status"],"overlap_days":row["overlap_days"],"days_since_resurfacing":row["days_since_resurfacing"],"overlap":{"start":row["overlap_start"],"end":row["overlap_end"]},"work_a":work("a"),"work_b":work("b"),"buffer_geometry_a":row["a_buffer"],"buffer_geometry_b":row["b_buffer"],"history":[{"title":x["action"].replace('_',' '),"detail":x["note"],"at":x["at"],"by":x["name"] or "Staff"} for x in history]}

@router.post("/conflicts/{alert_id}/decision")
def decide(alert_id:UUID,body:DecisionBody,db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    if len(body.note.strip())<15:raise HTTPException(422,"Decision note must be at least 15 characters")
    row=db.execute(text("select c.*,a.ward_id a_ward,a.agency_id a_agency,b.ward_id b_ward,b.agency_id b_agency from conflict_alert c join work a on a.id=c.work_a join work b on b.id=c.work_b where c.id=cast(:id as uuid) and c.tenant_id=cast(:tenant as uuid) for update of c"),{"id":str(alert_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row:raise HTTPException(404,"Conflict not found")
    _check_alert_scope(db,user,alert_id)
    if row["status"]!="open":raise HTTPException(409,"Conflict is already resolved")
    if body.action in ("coordinate_dates","reschedule"):
        if not body.work_id or not body.new_dates or not (body.new_dates.current_target_end or body.new_dates.planned_start):raise HTTPException(422,"Choose a work and provide at least one new date")
        work=db.execute(text("select planned_start,current_target_end,tenant_id from work where id=cast(:id as uuid) and id in (cast(:a as uuid),cast(:b as uuid))"),{"id":str(body.work_id),"a":str(row["work_a"]),"b":str(row["work_b"])}).mappings().first()
        if not work:raise HTTPException(422,"Chosen work must be part of this conflict")
        target=body.new_dates.current_target_end or work["current_target_end"]
        start=body.new_dates.planned_start or work["planned_start"]
        if target and start and target<start:raise HTTPException(422,"Target end must be on or after planned start")
        if target!=work["current_target_end"]:
            configured=db.execute(text("select reason_codes from city_config where tenant_id=cast(:tenant as uuid)"),{"tenant":str(user["tenant_id"])}).scalar() or []
            reason=body.reason_code or "utility_clash"
            if reason not in configured:raise HTTPException(422,"reason_code is not configured for this city")
            db.execute(text("insert into work_date_revision(tenant_id,work_id,old_target,new_target,reason_code,explanation,by_user,at) values(cast(:tenant as uuid),cast(:work as uuid),:old,:new,:reason,:note,cast(:actor as uuid),:at)"),{"tenant":str(user["tenant_id"]),"work":str(body.work_id),"old":work["current_target_end"],"new":target,"reason":body.reason_code or "utility_clash","note":body.note,"actor":str(user["id"]),"at":clock.now()})
        db.execute(text("update work set planned_start=:start,current_target_end=:target,updated_at=:at where id=cast(:id as uuid)"),{"start":start,"target":target,"at":clock.now(),"id":str(body.work_id)})
        emit(db,"WorkDatesRevised.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(body.work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"reason_code":body.reason_code or "utility_clash"})
    db.execute(text("insert into conflict_decision(tenant_id,alert_id,action,note,decided_by,at) values(cast(:tenant as uuid),cast(:id as uuid),cast(:action as conflict_action),:note,cast(:actor as uuid),:at)"),{"tenant":str(user["tenant_id"]),"id":str(alert_id),"action":body.action,"note":body.note,"actor":str(user["id"]),"at":clock.now()})
    db.execute(text("update conflict_alert set status='resolved' where id=cast(:id as uuid)"),{"id":str(alert_id)})
    db.execute(text("update permit set status='submitted' where work_id in (cast(:a as uuid),cast(:b as uuid)) and status in ('held','pending_coordination')"),{"a":str(row["work_a"]),"b":str(row["work_b"])})
    emit(db,"ConflictResolved.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(row["work_a"]),"conflict_id":str(alert_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"action":body.action})
    write_audit(db,user,"conflict_decided","conflict_alert",alert_id,after={"action":body.action,"note":body.note})
    db.commit();return {"id":str(alert_id),"status":"resolved","action":body.action}
