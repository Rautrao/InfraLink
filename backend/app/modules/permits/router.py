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
from app.core.security import check_jurisdiction,require_roles

router=APIRouter()
STAFF=("admin","commissioner","chief_engineer","superintending_engineer","executive_engineer","assistant_engineer","junior_engineer","utility_editor","auditor","traffic_police")
EDITORS=("admin","utility_editor")
class PermitCreate(BaseModel):
    work_id:UUID
    type:Literal["road_cut","row_utility","closure_noc"]
    valid_from:date|None=None
    valid_to:date|None=None
    deposit_amount:float|None=Field(default=None,ge=0)
    note:str|None=Field(default=None,max_length=2000)
class PermitDecision(BaseModel):
    action:Literal["approve","reject","hold"]
    note:str=Field(min_length=1,max_length=2000)
class DepositRelease(BaseModel):note:str=Field(min_length=1,max_length=1000)

def _scope(user):
    if user["role"] in ("admin","commissioner","chief_engineer","auditor","traffic_police"):return "true",{}
    if user["role"]=="junior_engineer":return ("w.ward_id=cast(:ward as uuid)",{"ward":str(user["ward_id"])} ) if user.get("ward_id") else ("false",{})
    if user["role"] in ("assistant_engineer","executive_engineer","superintending_engineer"):return ("wd.zone_id=cast(:zone as uuid)",{"zone":str(user["zone_id"])} ) if user.get("zone_id") else ("false",{})
    if user["role"]=="utility_editor":return ("w.agency_id=cast(:agency as uuid)",{"agency":str(user["agency_id"])} ) if user.get("agency_id") else ("false",{})
    return "false",{}

def _check_scope(db,user,work_id):
    scope,params=_scope(user)
    allowed=db.execute(text(f"select 1 from work w left join ward wd on wd.id=w.ward_id where w.id=cast(:id as uuid) and w.tenant_id=cast(:tenant as uuid) and {scope}"),{"id":str(work_id),"tenant":str(user["tenant_id"]),**params}).scalar()
    if not allowed:raise HTTPException(403,"Outside permit jurisdiction")

def _serialize(row):
    return {"id":str(row["id"]),"work_id":str(row["work_id"]),"work_ref_no":row["work_ref_no"],"work_title":row["work_title"],"agency_name":row["agency_name"],"type":row["type"],"status":row["status"],"applied_at":row["applied_at"],"valid_from":row["valid_from"],"valid_to":row["valid_to"],"deposit_amount":float(row["deposit_amount"]) if row["deposit_amount"] is not None else None,"deposit_status":row["deposit_status"],"has_open_conflict":bool(row["has_open_conflict"]),"conflict_summary":"An open utility conflict must be resolved before approval." if row["has_open_conflict"] else None}

@router.get("/permits/ping")
def ping():return {"module":"permits","status":"ready"}

@router.get("/permits")
def list_permits(status:str|None=None,db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    scope,params=_scope(user);params["tenant"]=str(user["tenant_id"])
    clauses=["p.tenant_id=cast(:tenant as uuid)",scope]
    if status:clauses.append("p.status::text=:status");params["status"]=status
    rows=db.execute(text(f"select p.*,p.type::text type,p.status::text status,p.deposit_status::text deposit_status,w.ref_no work_ref_no,w.title work_title,a.name agency_name,exists(select 1 from conflict_alert c where c.status='open' and (c.work_a=w.id or c.work_b=w.id)) has_open_conflict from permit p join work w on w.id=p.work_id left join ward wd on wd.id=w.ward_id join agency a on a.id=w.agency_id where {' and '.join(clauses)} order by p.applied_at desc"),params).mappings().all()
    return {"items":[_serialize(r) for r in rows],"total":len(rows)}

@router.post("/permits",status_code=201)
def create_permit(body:PermitCreate,db=Depends(get_db),user=Depends(require_roles(*EDITORS))):
    work=db.execute(text("select w.*,exists(select 1 from conflict_alert c where c.status='open' and (c.work_a=w.id or c.work_b=w.id)) has_conflict from work w where w.id=cast(:id as uuid) and w.tenant_id=cast(:tenant as uuid)"),{"id":str(body.work_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not work:raise HTTPException(422,"Register the work first")
    if work["geometry"] is None or work["planned_start"] is None or work["current_target_end"] is None:raise HTTPException(422,"Register the work first")
    _check_scope(db,user,body.work_id)
    from app.modules.conflict_engine.router import scan_conflicts
    scan_conflicts(db,user["tenant_id"],body.work_id)
    work=db.execute(text("select w.*,exists(select 1 from conflict_alert c where c.status='open' and (c.work_a=w.id or c.work_b=w.id)) has_conflict from work w where w.id=cast(:id as uuid) and w.tenant_id=cast(:tenant as uuid)"),{"id":str(body.work_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if body.valid_from and body.valid_to and body.valid_to<body.valid_from:raise HTTPException(422,"valid_to must be on or after valid_from")
    status="pending_coordination" if work["has_conflict"] else "submitted"
    pid=db.execute(text("insert into permit(tenant_id,work_id,type,status,applied_at,deposit_amount,deposit_status,valid_from,valid_to,note) values(cast(:tenant as uuid),cast(:work as uuid),cast(:type as permit_type),cast(:status as permit_status),:at,:deposit,case when :deposit is null then 'none'::deposit_status else 'held'::deposit_status end,:from,:to,:note) returning id"),{"tenant":str(user["tenant_id"]),"work":str(body.work_id),"type":body.type,"status":status,"at":clock.now(),"deposit":body.deposit_amount,"from":body.valid_from,"to":body.valid_to,"note":body.note}).scalar()
    if status=="pending_coordination":emit(db,"PermitHeld.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(body.work_id),"permit_id":str(pid),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat(),"reason":"utility_clash"})
    emit(db,"PermitSubmitted.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(body.work_id),"permit_id":str(pid),"actor_id":str(user["id"]),"occurred_at":clock.now().isoformat()})
    write_audit(db,user,"permit_submitted","permit",pid,after={"work_id":str(body.work_id),"type":body.type,"status":status})
    db.commit();return {"id":str(pid),"work_id":str(body.work_id),"type":body.type,"status":status}

@router.get("/permits/{permit_id}")
def permit_detail(permit_id:UUID,db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    row=db.execute(text("select p.*,p.type::text type,p.status::text status,p.deposit_status::text deposit_status,w.id work_id,w.ref_no work_ref_no,w.title work_title,w.road_name,w.status::text work_status,w.planned_start,w.current_target_end,w.ward_id,w.agency_id,a.name agency_name,exists(select 1 from conflict_alert c where c.status='open' and (c.work_a=w.id or c.work_b=w.id)) has_open_conflict from permit p join work w on w.id=p.work_id join agency a on a.id=w.agency_id where p.id=cast(:id as uuid) and p.tenant_id=cast(:tenant as uuid)"),{"id":str(permit_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row:raise HTTPException(404,"Permit not found")
    _check_scope(db,user,row["work_id"])
    conflicts=db.execute(text("select id,type::text type,status::text status from conflict_alert where status='open' and (work_a=cast(:work as uuid) or work_b=cast(:work as uuid))"),{"work":str(row["work_id"])}).mappings().all()
    events=db.execute(text("select action,after,at,actor_id from audit_log where entity='permit' and entity_id=:id order by at"),{"id":str(permit_id)}).mappings().all()
    return {**_serialize(row),"restoration_verified":row["work_status"]=="restoration_verified","work":{"id":str(row["work_id"]),"ref_no":row["work_ref_no"],"title":row["work_title"],"road_name":row["road_name"],"status":row["work_status"],"planned_start":row["planned_start"],"current_target_end":row["current_target_end"],"agency":{"name":row["agency_name"]}},"conflicts":[{**dict(x),"id":str(x["id"])} for x in conflicts],"history":[{"title":x["action"].replace('_',' '),"detail":x["after"],"at":x["at"],"by":str(x["actor_id"]) if x["actor_id"] else "System"} for x in events]}

@router.post("/permits/{permit_id}/decision")
def decide(permit_id:UUID,body:PermitDecision,db=Depends(get_db),user=Depends(require_roles(*STAFF))):
    row=db.execute(text("select p.*,p.type::text type,p.status::text status,w.id work_id,w.status::text work_status,w.ward_id,w.agency_id,exists(select 1 from conflict_alert c where c.status='open' and (c.work_a=w.id or c.work_b=w.id)) has_open_conflict from permit p join work w on w.id=p.work_id where p.id=cast(:id as uuid) and p.tenant_id=cast(:tenant as uuid) for update of p"),{"id":str(permit_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row:raise HTTPException(404,"Permit not found")
    _check_scope(db,user,row["work_id"])
    if row["status"] not in ("submitted","pending_coordination","held"):raise HTTPException(409,"Only a submitted or held permit can receive a decision")
    if body.action=="approve":
        if row["has_open_conflict"]:raise HTTPException(409,detail={"code":"PENDING_COORDINATION","message":"Resolve all open conflicts before approving this permit."})
        if row["type"]=="closure_noc" and user["role"]!="traffic_police":raise HTTPException(403,"Closure NOC approval is restricted to traffic_police")
        if row["type"]=="road_cut" and user["role"] not in ("executive_engineer","assistant_engineer"):raise HTTPException(403,"Road cut approval is restricted to EE/AE")
        new_status="approved"
    elif body.action=="reject":new_status="rejected"
    else:new_status="held"
    at=clock.now()
    db.execute(text("update permit set status=cast(:status as permit_status),approved_by=case when :status='approved' then cast(:actor as uuid) else approved_by end,approved_at=case when :status='approved' then :at else approved_at end,note=concat_ws(E'\\n',nullif(note,''),cast(:note as text)) where id=cast(:id as uuid)"),{"status":new_status,"actor":str(user["id"]),"at":at,"note":body.note,"id":str(permit_id)})
    if new_status=="approved":
        if row["work_status"]=="planned":
            db.execute(text("update work set status='permitted',updated_at=:at where id=cast(:work as uuid)"),{"at":at,"work":str(row["work_id"])})
            db.execute(text("insert into work_status_history(tenant_id,work_id,from_status,to_status,reason_code,explanation,by_user,at) values(cast(:tenant as uuid),cast(:work as uuid),'planned','permitted','permit_approved',:note,cast(:actor as uuid),:at)"),{"tenant":str(user["tenant_id"]),"work":str(row["work_id"]),"note":body.note,"actor":str(user["id"]),"at":at})
        emit(db,"PermitApproved.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(row["work_id"]),"permit_id":str(permit_id),"actor_id":str(user["id"]),"occurred_at":at.isoformat()})
    if new_status=="held":emit(db,"PermitHeld.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(row["work_id"]),"permit_id":str(permit_id),"actor_id":str(user["id"]),"occurred_at":at.isoformat(),"reason":body.note})
    write_audit(db,user,f"permit_{new_status}","permit",permit_id,after={"status":new_status,"note":body.note});db.commit()
    return {"id":str(permit_id),"status":new_status}

@router.post("/permits/{permit_id}/deposit/release")
def release_deposit(permit_id:UUID,body:DepositRelease,db=Depends(get_db),user=Depends(require_roles("admin","commissioner","chief_engineer","executive_engineer","assistant_engineer"))):
    row=db.execute(text("select p.*,w.status::text work_status,w.ward_id,w.agency_id from permit p join work w on w.id=p.work_id where p.id=cast(:id as uuid) and p.tenant_id=cast(:tenant as uuid) for update of p"),{"id":str(permit_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row:raise HTTPException(404,"Permit not found")
    _check_scope(db,user,row["work_id"])
    if row["work_status"]!="restoration_verified":raise HTTPException(409,"Deposit release requires restoration_verified")
    if row["deposit_status"]!="held":raise HTTPException(409,"Deposit is not held")
    db.execute(text("update permit set deposit_status='released',note=concat_ws(E'\\n',nullif(note,''),cast(:note as text)) where id=cast(:id as uuid)"),{"id":str(permit_id),"note":body.note});write_audit(db,user,"deposit_released","permit",permit_id,after={"deposit_status":"released","note":body.note});db.commit();return {"id":str(permit_id),"deposit_status":"released"}
