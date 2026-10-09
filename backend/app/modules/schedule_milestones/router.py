from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from app.core import clock
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.events import emit
from app.core.security import check_jurisdiction, require_roles
from app.modules.project_registry.router import WORK_EDIT_ROLES

router = APIRouter()

class DateRevision(BaseModel):
    new_target_end: date
    reason_code: str = Field(min_length=1)
    explanation: str = Field(min_length=15)

class MilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    planned_date: date | None = None
    actual_date: date | None = None
    pct: int = Field(default=0, ge=0, le=100)
    sort: int = 0

class MilestonePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    planned_date: date | None = None
    actual_date: date | None = None
    pct: int | None = Field(default=None, ge=0, le=100)
    sort: int | None = None

def _load_work(db, work_id, user):
    row=db.execute(text("select id,tenant_id,ward_id,agency_id,current_target_end,original_target_end from work where id=cast(:id as uuid) and tenant_id=cast(:tenant as uuid)"),{"id":str(work_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row: raise HTTPException(404,"Work not found")
    check_jurisdiction(user,row["ward_id"],row["agency_id"])
    return row

def _recompute_pct(db, work_id):
    db.execute(text("""
        update work set pct_complete=(select round(avg(pct))::int from work_milestone where work_id=cast(:id as uuid)),updated_at=:at
        where id=cast(:id as uuid) and exists(select 1 from work_milestone where work_id=cast(:id as uuid))
    """),{"id":str(work_id),"at":clock.now()})

@router.get("/schedule_milestones/ping")
def ping(): return {"module":"schedule_milestones","status":"ready"}

@router.post("/works/{work_id}/dates")
def revise_dates(work_id: UUID, body: DateRevision, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    work=_load_work(db,work_id,user)
    reason_codes=db.execute(text("select reason_codes from city_config where tenant_id=cast(:tenant as uuid)"),{"tenant":str(user["tenant_id"])}).scalar() or []
    if body.reason_code not in reason_codes: raise HTTPException(422,"reason_code is not configured for this city")
    old_target=work["current_target_end"]
    if body.new_target_end==old_target: raise HTTPException(422,"new_target_end must change the current target")
    db.execute(text("insert into work_date_revision(tenant_id,work_id,old_target,new_target,reason_code,explanation,by_user,at) values(cast(:tenant as uuid),cast(:work as uuid),:old,:new,:reason,:explanation,cast(:actor as uuid),:at)"),{"tenant":str(user["tenant_id"]),"work":str(work_id),"old":old_target,"new":body.new_target_end,"reason":body.reason_code,"explanation":body.explanation,"actor":str(user["id"]),"at":clock.now()})
    db.execute(text("update work set current_target_end=:target,updated_at=:at where id=cast(:id as uuid)"),{"target":body.new_target_end,"at":clock.now(),"id":str(work_id)})
    emit(db,"WorkDatesRevised.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(work_id),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"old_target":old_target.isoformat(),"new_target":body.new_target_end.isoformat(),"reason_code":body.reason_code,"explanation":body.explanation})
    write_audit(db,user,"date_revised","work",work_id,before={"current_target_end":old_target},after={"current_target_end":body.new_target_end,"reason_code":body.reason_code,"explanation":body.explanation})
    db.commit()
    return {"work_id":str(work_id),"old_target":old_target,"new_target":body.new_target_end,"reason_code":body.reason_code,"explanation":body.explanation}

@router.post("/works/{work_id}/milestones",status_code=201)
def create_milestone(work_id: UUID, body: MilestoneCreate, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    work=_load_work(db,work_id,user)
    pct=100 if body.actual_date else body.pct
    milestone_id=db.execute(text("""
        insert into work_milestone(tenant_id,work_id,name,planned_date,actual_date,pct,sort)
        values(cast(:tenant as uuid),cast(:work as uuid),:name,:planned,:actual,:pct,:sort) returning id
    """),{"tenant":str(user["tenant_id"]),"work":str(work_id),"name":body.name,"planned":body.planned_date,"actual":body.actual_date,"pct":pct,"sort":body.sort}).scalar()
    _recompute_pct(db,work_id)
    write_audit(db,user,"milestone_created","work_milestone",milestone_id,after={"work_id":str(work_id),"name":body.name,"pct":pct})
    db.commit()
    return {"id":str(milestone_id),"work_id":str(work_id),"name":body.name,"planned_date":body.planned_date,"actual_date":body.actual_date,"pct":pct,"sort":body.sort}

@router.patch("/milestones/{milestone_id}")
def patch_milestone(milestone_id: UUID, body: MilestonePatch, db=Depends(get_db), user=Depends(require_roles(*WORK_EDIT_ROLES))):
    milestone=db.execute(text("select m.*,w.ward_id,w.agency_id from work_milestone m join work w on w.id=m.work_id where m.id=cast(:id as uuid) and m.tenant_id=cast(:tenant as uuid)"),{"id":str(milestone_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not milestone: raise HTTPException(404,"Milestone not found")
    check_jurisdiction(user,milestone["ward_id"],milestone["agency_id"])
    changes=body.model_dump(exclude_unset=True)
    if not changes: return {k:milestone[k] for k in ("id","work_id","name","planned_date","actual_date","pct","sort")}
    before={k:milestone[k] for k in changes}
    if changes.get("actual_date") is not None:
        changes["pct"]=100
    assignments=[]; params={"id":str(milestone_id)}
    for key,value in changes.items(): assignments.append(f"{key}=:{key}"); params[key]=value
    db.execute(text(f"update work_milestone set {','.join(assignments)} where id=cast(:id as uuid)"),params)
    _recompute_pct(db,milestone["work_id"])
    write_audit(db,user,"milestone_updated","work_milestone",milestone_id,before=before,after=changes)
    db.commit()
    result=db.execute(text("select id,work_id,name,planned_date,actual_date,pct,sort from work_milestone where id=cast(:id as uuid)"),{"id":str(milestone_id)}).mappings().one()
    return {**dict(result),"id":str(result["id"]),"work_id":str(result["work_id"])}
