from time import monotonic
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from app.core import clock
from app.core.db import get_db
from app.core.security import require_roles

router=APIRouter()
STAFF=("admin","commissioner","chief_engineer","superintending_engineer","executive_engineer","assistant_engineer","junior_engineer","utility_editor","contractor","auditor","traffic_police")
_summary_cache={}

def _scope(user,alias="w"):
    if user["role"] in ("admin","commissioner","chief_engineer","auditor"): return "true",{}
    if user["role"]=="junior_engineer": return (f"{alias}.ward_id=cast(:scope_ward as uuid)",{"scope_ward":str(user["ward_id"])} ) if user.get("ward_id") else ("false",{})
    if user["role"] in ("assistant_engineer","executive_engineer","superintending_engineer"):
        return ("wd.zone_id=cast(:scope_zone as uuid)",{"scope_zone":str(user["zone_id"])} ) if user.get("zone_id") else ("false",{})
    if user["role"]=="utility_editor": return (f"{alias}.agency_id=cast(:scope_agency as uuid)",{"scope_agency":str(user["agency_id"])} ) if user.get("agency_id") else ("false",{})
    return "false",{}

@router.get("/reports/summary")
def summary(db=Depends(get_db)):
    tenant=db.execute(text("select id from tenant order by slug limit 1")).scalar()
    cache_key=str(tenant)
    cached=_summary_cache.get(cache_key)
    if cached and monotonic()-cached[0]<30:return cached[1]
    row=db.execute(text("""select count(*) filter(where w.status::text in ('planned','permitted','ongoing','paused')) active,
      count(*) filter(where w.status::text='ongoing') ongoing,
      count(*) filter(where w.current_target_end<:today and w.status::text not in ('completed','restoration_verified','closed')) delayed,
      count(*) filter(where w.status::text in ('ongoing','permitted','paused') and (w.last_update_at is null or w.last_update_at<:now-make_interval(days=>coalesce(c.overdue_days,7)))) overdue_updates,
      count(*) filter(where w.status::text in ('completed','restoration_verified','closed') and w.actual_end>=date_trunc('month',cast(:today as date))::date) completed_this_month,
      count(*) total from work w left join city_config c on c.tenant_id=w.tenant_id where w.is_public"""),{"today":clock.today(),"now":clock.now()}).mappings().one()
    result={**dict(row),"as_of":clock.now()};_summary_cache[cache_key]=(monotonic(),result);return result

@router.get("/reports/delayed")
def delayed(db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    scope,params=_scope(user);params.update({"tenant":str(user["tenant_id"]),"today":clock.today()})
    rows=db.execute(text(f"select w.id,w.ref_no,w.title,w.road_name,wd.name ward_name,a.name agency_name,w.status::text status,w.current_target_end,w.planned_start,w.pct_complete,:today-w.current_target_end days_late from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id where w.tenant_id=cast(:tenant as uuid) and w.current_target_end<:today and w.status::text not in ('completed','restoration_verified','closed') and {scope} order by days_late desc"),params).mappings().all()
    return {"items":[{**dict(r),"id":str(r["id"])} for r in rows],"total":len(rows),"as_of":clock.today()}

@router.get("/reports/overdue-updates")
def overdue_updates(db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    scope,params=_scope(user);params.update({"tenant":str(user["tenant_id"]),"now":clock.now()})
    rows=db.execute(text(f"select w.id,w.ref_no,w.title,w.road_name,wd.name ward_name,a.name agency_name,w.status::text status,w.last_update_at,coalesce(c.overdue_days,7) overdue_days,extract(epoch from (:now-coalesce(w.last_update_at,w.created_at)))/86400 days_since_update from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id left join city_config c on c.tenant_id=w.tenant_id where w.tenant_id=cast(:tenant as uuid) and w.status::text in ('ongoing','permitted','paused') and (w.last_update_at is null or w.last_update_at<:now-make_interval(days=>coalesce(c.overdue_days,7))) and {scope} order by w.last_update_at nulls first"),params).mappings().all()
    return {"items":[{**dict(r),"id":str(r["id"])} for r in rows],"total":len(rows),"as_of":clock.now()}

@router.get("/reports/repeat-dig")
def repeat_dig(months:int=Query(12,ge=1,le=120),db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    scope,params=_scope(user);params.update({"tenant":str(user["tenant_id"]),"months":months,"today":clock.today()})
    rows=db.execute(text(f"""with pair as (select w.id,w.ref_no,w.title,w.road_name,w.ward_id,w.agency_id,w.geometry,w.planned_start,w.actual_end,w.created_at from work w left join ward wd on wd.id=w.ward_id where w.tenant_id=cast(:tenant as uuid) and w.geometry is not null and coalesce(w.actual_end,w.created_at::date)>=:today-make_interval(months=>:months) and {scope}), clusters as (select a.id a_id,b.id b_id,a.road_name,coalesce(a.ward_id,b.ward_id) ward_id,least(a.planned_start,b.planned_start) first_start,greatest(coalesce(a.actual_end,a.created_at::date),coalesce(b.actual_end,b.created_at::date)) last_end from pair a join pair b on a.id<b.id and a.geometry && b.geometry and ST_DWithin(ST_Transform(a.geometry,32643),ST_Transform(b.geometry,32643),15)) select c.road_name,wd.name ward_name,count(distinct p.id) work_count,json_agg(distinct jsonb_build_object('id',p.id,'ref_no',p.ref_no,'title',p.title,'agency',ag.name)) works,min(c.first_start) first_start,max(c.last_end) last_end from clusters c join pair p on p.id in (c.a_id,c.b_id) left join ward wd on wd.id=c.ward_id join agency ag on ag.id=p.agency_id group by c.road_name,wd.name having count(distinct p.id)>=2 order by work_count desc"""),params).mappings().all()
    return {"items":[dict(r) for r in rows],"months":months,"total":len(rows)}

@router.get("/staff/inbox")
def staff_inbox(db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    scope,params=_scope(user);params["tenant"]=str(user["tenant_id"]);params["now"]=clock.now();params["today"]=clock.today()
    works=db.execute(text(f"select 'delayed' kind,w.id,w.ref_no,w.title,w.road_name,wd.name ward_name,w.current_target_end::text due_at,w.status::text status from work w left join ward wd on wd.id=w.ward_id where w.tenant_id=cast(:tenant as uuid) and w.current_target_end<:today and w.status::text not in ('completed','restoration_verified','closed') and {scope} union all select 'overdue_update',w.id,w.ref_no,w.title,w.road_name,wd.name ward_name,w.last_update_at::text due_at,w.status::text status from work w left join ward wd on wd.id=w.ward_id left join city_config c on c.tenant_id=w.tenant_id where w.tenant_id=cast(:tenant as uuid) and w.status::text in ('ongoing','permitted','paused') and (w.last_update_at is null or w.last_update_at<:now-make_interval(days=>coalesce(c.overdue_days,7))) and {scope} order by due_at nulls first"),params).mappings().all()
    tickets=db.execute(text(f"select t.id,t.ref_no,t.kind,t.status::text status,t.current_level,t.created_at,t.escalated_at,w.id work_id,w.title,w.road_name,wd.name ward_name,(w.status::text='ongoing' and (select count(*) from feedback_ticket v where v.work_id=w.id and v.kind='still_ongoing_no' and v.created_at>=:now-interval '7 days')>=3) possibly_stale_data from feedback_ticket t join work w on w.id=t.work_id left join ward wd on wd.id=w.ward_id where t.tenant_id=cast(:tenant as uuid) and t.status not in ('resolved','closed') and t.last_response_at is null and {scope.replace('w.', 'w.')} order by t.created_at"),{"tenant":str(user["tenant_id"]),"now":clock.now(),**{k:v for k,v in params.items() if k.startswith("scope_")}}).mappings().all()
    conflict_scope=scope.replace("w.","a.")
    conflicts=db.execute(text(f"select c.id,c.type::text kind,a.ref_no||' · '||b.ref_no title,a.road_name,wd.name ward_name,c.detected_at due_at,'open' status from conflict_alert c join work a on a.id=c.work_a join work b on b.id=c.work_b left join ward wd on wd.id=a.ward_id where c.tenant_id=cast(:tenant as uuid) and c.status='open' and {conflict_scope} order by c.detected_at"),{"tenant":str(user["tenant_id"]),**{k:v for k,v in params.items() if k.startswith("scope_")}}).mappings().all()
    return {"works":[{**dict(x),"id":str(x["id"])} for x in works],"feedback":[{**dict(x),"id":str(x["id"]),"work_id":str(x["work_id"])} for x in tickets],"conflicts":[{**dict(x),"id":str(x["id"])} for x in conflicts],"total":len(works)+len(tickets)+len(conflicts),"as_of":clock.now()}
