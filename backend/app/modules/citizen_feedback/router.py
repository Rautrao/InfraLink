from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID
import re

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core import clock
from app.core.config import settings
from app.core.db import get_db
from app.core.events import emit
from app.core.audit import write_audit
from app.core.security import get_current_user, require_roles
from app.modules.organisations.service import get_assignee

router = APIRouter()
STAFF_ROLES = ("admin", "commissioner", "chief_engineer", "superintending_engineer", "executive_engineer", "assistant_engineer", "junior_engineer", "utility_editor", "contractor", "auditor", "traffic_police")
RESIDENT_ROLES = ("resident",)

class ResponseBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    status: str = "in_progress"
    make_public: bool = False

class ModerateBody(BaseModel):
    approve: bool

def _work(db, work_id, tenant):
    row = db.execute(text("select w.*,a.name agency_name,wd.name ward_name from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id where w.id=cast(:id as uuid) and w.tenant_id=cast(:tenant as uuid)"), {"id": str(work_id), "tenant": str(tenant)}).mappings().first()
    if not row: raise HTTPException(404, "Work not found")
    return row

def _ticket(db, ref_no, user, lock=False):
    row = db.execute(text("select t.*,w.title work_title,w.ref_no work_ref,w.road_name,w.ward_id,w.tenant_id work_tenant,u.name resident_name from feedback_ticket t join work w on w.id=t.work_id join app_user u on u.id=t.resident_id where t.ref_no=:ref and t.tenant_id=cast(:tenant as uuid)" + (" for update of t" if lock else "")), {"ref": ref_no, "tenant": str(user["tenant_id"])}).mappings().first()
    if not row: raise HTTPException(404, "Feedback ticket not found")
    if user["role"] == "resident" and str(row["resident_id"]) != str(user["id"]): raise HTTPException(404, "Feedback ticket not found")
    return row

def _history(db, row, resident):
    events = db.execute(text("select id,status::text as status,responder_id,message,is_public,at from ticket_event where ticket_id=cast(:id as uuid) order by at,id"), {"id": str(row["id"])}).mappings().all()
    return [{"id":str(e["id"]),"status":e["status"],"responder_id":str(e["responder_id"]) if e["responder_id"] else None,"message":e["message"] if not resident or e["is_public"] else None,"is_public":bool(e["is_public"]),"at":e["at"]} for e in events]

def _ticket_dict(db, row, resident):
    return {"id":str(row["id"]),"ref_no":row["ref_no"],"work_id":str(row["work_id"]),"work_ref_no":row["work_ref"],"work_title":row["work_title"],"road_name":row["road_name"],"kind":row["kind"],"text":row["text"],"photo_url":f"/api/v1/feedback/{row['ref_no']}/photo" if row["photo_path"] else None,"lat":row["lat"],"lon":row["lon"],"status":row["status"],"current_level":row["current_level"],"assigned_to":str(row["assigned_to"]) if row["assigned_to"] else None,"is_public":row["is_public"],"moderation":row["moderation"],"overdue_public":row.get("overdue_public",False),"created_at":row["created_at"],"last_response_at":row["last_response_at"],"escalated_at":row["escalated_at"],"history":_history(db,row,resident)}

def _next_ref(db, tenant):
    year = clock.now().year
    db.execute(text("select pg_advisory_xact_lock(hashtext(:key))"), {"key":f"feedback:{tenant}:{year}"})
    n = db.execute(text("select coalesce(max(split_part(ref_no,'-',3)::int),0)+1 from feedback_ticket where tenant_id=cast(:tenant as uuid) and ref_no like :prefix"), {"tenant":str(tenant),"prefix":f"FB-{year}-%"}).scalar()
    return f"FB-{year}-{n:06d}"

def _photo_bytes(upload: UploadFile | None):
    if not upload: return None
    raw = upload.file.read()
    if not raw: return None
    if len(raw)>5*1024*1024:raise HTTPException(413,"Photo must be 5 MB or smaller")
    try:
        from PIL import Image
        image = Image.open(BytesIO(raw))
        image.load()
        clean = Image.new(image.mode, image.size)
        clean.putdata(list(image.getdata()))
        output = BytesIO()
        clean.save(output, format="PNG" if image.mode in ("RGBA", "LA") else "JPEG", quality=88)
        suffix = ".png" if image.mode in ("RGBA", "LA") else ".jpg"
        return suffix, output.getvalue()
    except Exception as exc:
        raise HTTPException(422, "Photo must be a valid image") from exc

def _store_photo(upload):
    if not upload: return None
    suffix, data = upload
    root = Path(settings.upload_dir).parent / "feedback-private"
    root.mkdir(parents=True, exist_ok=True)
    name = f"{UUID(int=__import__('secrets').randbits(128))}{suffix}"
    (root / name).write_bytes(data)
    return name

@router.post("/works/{work_id}/feedback", status_code=201)
def submit_feedback(work_id: UUID, kind: str = Form(...), text_value: str = Form(..., alias="text", max_length=500), lat: float | None = Form(None), lon: float | None = Form(None), photo: UploadFile | None = File(None), captcha: str | None = Header(None, alias="X-Captcha-Token"), db=Depends(get_db), user=Depends(require_roles(*RESIDENT_ROLES))):
    if kind not in ("question", "complaint", "observation"): raise HTTPException(422, "Invalid feedback kind")
    if not text_value.strip(): raise HTTPException(422, "Feedback text cannot be blank")
    if (lat is None)!=(lon is None) or (lat is not None and not -90<=lat<=90) or (lon is not None and not -180<=lon<=180):raise HTTPException(422,"lat and lon must be provided together within geographic bounds")
    work = _work(db, work_id, user["tenant_id"])
    recent = db.execute(text("select count(*) from feedback_ticket where resident_id=cast(:user as uuid) and created_at >= :since and kind in ('question','complaint','observation')"), {"user":str(user["id"]),"since":clock.now()-timedelta(hours=1)}).scalar()
    if recent >= 5: raise HTTPException(429, "Feedback limit reached; try again in an hour")
    clean_photo = _photo_bytes(photo)
    photo_path = _store_photo(clean_photo)
    ref = _next_ref(db, user["tenant_id"])
    assignee = get_assignee(work, 1, db)
    ticket_id = db.execute(text("insert into feedback_ticket(tenant_id,ref_no,work_id,resident_id,kind,text,photo_path,lat,lon,status,current_level,assigned_to,is_public,moderation,created_at) values(cast(:tenant as uuid),:ref,cast(:work as uuid),cast(:resident as uuid),cast(:kind as feedback_kind),:body,:photo,:lat,:lon,'open',1,cast(:assigned as uuid),false,'pending',:at) returning id"), {"tenant":str(user["tenant_id"]),"ref":ref,"work":str(work_id),"resident":str(user["id"]),"kind":kind,"body":text_value.strip(),"photo":photo_path,"lat":lat,"lon":lon,"assigned":str(assignee["id"]) if assignee else None,"at":clock.now()}).scalar()
    db.execute(text("insert into ticket_event(tenant_id,ticket_id,status,message,is_public,at) values(cast(:tenant as uuid),cast(:id as uuid),'open','Received',false,:at)"), {"tenant":str(user["tenant_id"]),"id":str(ticket_id),"at":clock.now()})
    emit(db,"FeedbackSubmitted.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(work_id),"ticket_id":str(ticket_id),"ref_no":ref,"resident_id":str(user["id"]),"occurred_at":clock.now().isoformat()})
    db.commit()
    row = _ticket(db,ref,user)
    return _ticket_dict(db,row,True)

@router.get("/feedback/mine")
def mine(db=Depends(get_db),user=Depends(require_roles(*RESIDENT_ROLES))):
    rows=db.execute(text("select ref_no from feedback_ticket where tenant_id=cast(:tenant as uuid) and resident_id=cast(:user as uuid) order by created_at desc"),{"tenant":str(user["tenant_id"]),"user":str(user["id"])}).scalars().all()
    return {"items":[_ticket_dict(db,_ticket(db,r,user),True) for r in rows]}

@router.get("/feedback/{ref_no}")
def get_feedback(ref_no: str,db=Depends(get_db),user=Depends(get_current_user)):
    row=_ticket(db,ref_no,user)
    return _ticket_dict(db,row,user["role"]=="resident")

@router.get("/feedback/{ref_no}/photo")
def feedback_photo(ref_no:str,db=Depends(get_db),user=Depends(get_current_user)):
    row=_ticket(db,ref_no,user)
    if not row["photo_path"]:raise HTTPException(404,"Feedback has no photo")
    path=Path(settings.upload_dir).parent/"feedback-private"/row["photo_path"]
    if not path.is_file():raise HTTPException(404,"Feedback photo not found")
    media="image/jpeg" if path.suffix.lower() in (".jpg",".jpeg") else "image/png"
    return FileResponse(path,media_type=media,filename=path.name)

@router.get("/works/{work_id}/feedback/public")
def public_feedback(work_id: UUID,db=Depends(get_db)):
    rows=db.execute(text("select t.id,t.ref_no,t.kind,t.text,t.created_at,u.name resident_name,u.phone resident_phone,u.email resident_email from feedback_ticket t join app_user u on u.id=t.resident_id join work w on w.id=t.work_id where t.work_id=cast(:work as uuid) and w.is_public and t.is_public and t.moderation='approved' order by t.created_at desc"),{"work":str(work_id)}).mappings().all()
    result=[]
    for row in rows:
        responses=db.execute(text("select message,at from ticket_event where ticket_id=cast(:id as uuid) and is_public and responder_id is not null order by at"),{"id":str(row["id"])}).mappings().all()
        safe_text=_redact(row["text"],row)
        result.append({"ref_no":row["ref_no"],"kind":row["kind"],"text":safe_text,"resident":"Resident","created_at":row["created_at"],"responses":[{"message":_redact(x["message"],row),"at":x["at"]} for x in responses]})
    return {"items":result}

def _redact(value,person):
    if not value:return value
    result=re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\+?\d[\d ()-]{7,}\d", "[redacted]", value, flags=re.I)
    for private in (person.get("resident_name"),person.get("resident_email"),person.get("resident_phone")):
        if private:
            result=re.sub(re.escape(str(private)),"[redacted]",result,flags=re.I)
            first=str(private).strip().split(" ")[0]
            if len(first)>2:result=re.sub(rf"\b{re.escape(first)}\b","[redacted]",result,flags=re.I)
    return result

def _scope(user):
    if user["role"] in ("admin","commissioner","chief_engineer","auditor"): return "true",{}
    if user["role"]=="junior_engineer": return ("w.ward_id=cast(:scope_ward as uuid)",{"scope_ward":str(user["ward_id"])} ) if user.get("ward_id") else ("false",{})
    if user["role"] in ("assistant_engineer","executive_engineer","superintending_engineer"):
        return ("wd.zone_id=cast(:scope_zone as uuid)",{"scope_zone":str(user["zone_id"])} ) if user.get("zone_id") else ("false",{})
    if user["role"]=="utility_editor": return ("w.agency_id=cast(:scope_agency as uuid)",{"scope_agency":str(user["agency_id"])} ) if user.get("agency_id") else ("false",{})
    return "false",{}

@router.get("/staff/feedback")
def staff_feedback(status: str | None=None,awaiting: bool=False,level: int | None=Query(None,ge=1,le=4),ward_id: UUID | None=None,db=Depends(get_db),user=Depends(require_roles(*STAFF_ROLES))):
    scope,params=_scope(user); clauses=["t.tenant_id=cast(:tenant as uuid)",scope];params["tenant"]=str(user["tenant_id"])
    if status: clauses.append("t.status::text=:status");params["status"]=status
    if awaiting: clauses.append("t.last_response_at is null")
    if level: clauses.append("t.current_level=:level");params["level"]=level
    if ward_id: clauses.append("w.ward_id=cast(:ward as uuid)");params["ward"]=str(ward_id)
    rows=db.execute(text(f"select t.*,w.title work_title,w.ref_no work_ref,w.road_name,wd.name ward_name,u.name resident_name,extract(epoch from (:now-t.created_at))/86400 sla_age_days,(select count(*) from ticket_event e where e.ticket_id=t.id and e.responder_id is not null) response_count,(w.status::text='ongoing' and (select count(*) from feedback_ticket v where v.work_id=w.id and v.kind='still_ongoing_no' and v.created_at>=:now-interval '7 days')>=3) possibly_stale_data from feedback_ticket t join work w on w.id=t.work_id left join ward wd on wd.id=w.ward_id join app_user u on u.id=t.resident_id where {' and '.join(clauses)} order by (t.last_response_at is null) desc,t.created_at"),{**params,"now":clock.now()}).mappings().all()
    items=[]
    for row in rows:
        value=_ticket_dict(db,row,False); value.update({"resident_name":row["resident_name"],"ward_name":row["ward_name"],"sla_age_days":round(float(row["sla_age_days"] or 0),2),"awaiting_response":row["response_count"]==0,"possibly_stale_data":bool(row["possibly_stale_data"])})
        items.append(value)
    return {"items":items,"total":len(items)}

@router.post("/staff/feedback/{ticket_id}/respond")
def respond(ticket_id: UUID,body: ResponseBody,db=Depends(get_db),user=Depends(require_roles(*STAFF_ROLES))):
    row=db.execute(text("select t.*,w.ward_id,w.agency_id from feedback_ticket t join work w on w.id=t.work_id where t.id=cast(:id as uuid) and t.tenant_id=cast(:tenant as uuid) for update of t"),{"id":str(ticket_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row: raise HTTPException(404,"Feedback ticket not found")
    scope,params=_scope(user); visible=db.execute(text(f"select 1 from work w left join ward wd on wd.id=w.ward_id where w.id=cast(:id as uuid) and {scope}"),{"id":str(row["work_id"]),**params}).scalar()
    if not visible: raise HTTPException(403,"Outside jurisdiction")
    if body.status not in ("acknowledged","in_progress","resolved","closed"): raise HTTPException(422,"Invalid response status")
    at=clock.now()
    db.execute(text("update feedback_ticket set status=cast(:status as feedback_status),last_response_at=:at where id=cast(:id as uuid)"),{"status":body.status,"at":at,"id":str(ticket_id)})
    db.execute(text("insert into ticket_event(tenant_id,ticket_id,status,responder_id,message,is_public,at) values(cast(:tenant as uuid),cast(:id as uuid),cast(:status as feedback_status),cast(:actor as uuid),:message,:public,:at)"),{"tenant":str(user["tenant_id"]),"id":str(ticket_id),"actor":str(user["id"]),"status":body.status,"message":body.message,"public":body.make_public,"at":at})
    emit(db,"FeedbackResponded.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(row["work_id"]),"ticket_id":str(ticket_id),"resident_id":str(row["resident_id"]),"status":body.status,"occurred_at":at.isoformat()})
    write_audit(db,user,"feedback_responded","feedback_ticket",ticket_id,after={"status":body.status,"message":body.message,"is_public":body.make_public})
    db.commit()
    return {"status":"ok","last_response_at":at}

@router.post("/staff/feedback/{ticket_id}/moderate")
def moderate(ticket_id: UUID,body:ModerateBody,db=Depends(get_db),user=Depends(require_roles(*STAFF_ROLES))):
    row=db.execute(text("select * from feedback_ticket where id=cast(:id as uuid) and tenant_id=cast(:tenant as uuid) for update"),{"id":str(ticket_id),"tenant":str(user["tenant_id"])}).mappings().first()
    if not row: raise HTTPException(404,"Feedback ticket not found")
    scope,params=_scope(user); allowed=db.execute(text(f"select 1 from work w left join ward wd on wd.id=w.ward_id where w.id=cast(:work as uuid) and {scope}"),{"work":str(row["work_id"]),**params}).scalar()
    if not allowed: raise HTTPException(403,"Outside jurisdiction")
    moderation="approved" if body.approve else "rejected"
    db.execute(text("update feedback_ticket set moderation=cast(:moderation as moderation_status),is_public=:public where id=cast(:id as uuid)"),{"moderation":moderation,"public":body.approve,"id":str(ticket_id)})
    write_audit(db,user,"feedback_moderated","feedback_ticket",ticket_id,after={"moderation":moderation,"is_public":body.approve})
    db.commit()
    return {"id":str(ticket_id),"moderation":moderation,"is_public":body.approve}

class OngoingBody(BaseModel): value: bool

@router.post("/works/{work_id}/still-ongoing",status_code=201)
def still_ongoing(work_id:UUID,body:OngoingBody,db=Depends(get_db),user=Depends(require_roles(*RESIDENT_ROLES))):
    work=_work(db,work_id,user["tenant_id"])
    recent=db.execute(text("select 1 from feedback_ticket where work_id=cast(:work as uuid) and resident_id=cast(:user as uuid) and kind in ('still_ongoing_yes','still_ongoing_no') and created_at>:since"),{"work":str(work_id),"user":str(user["id"]),"since":clock.now()-timedelta(hours=24)}).scalar()
    if recent: raise HTTPException(429,"You have already confirmed this work in the last 24 hours")
    level=1; assignee=get_assignee(work,level,db); ref=_next_ref(db,user["tenant_id"]); kind="still_ongoing_yes" if body.value else "still_ongoing_no"; at=clock.now()
    ticket=db.execute(text("insert into feedback_ticket(tenant_id,ref_no,work_id,resident_id,kind,text,status,current_level,assigned_to,is_public,moderation,created_at) values(cast(:tenant as uuid),:ref,cast(:work as uuid),cast(:resident as uuid),cast(:kind as feedback_kind),:body,'open',:level,cast(:assigned as uuid),false,'pending',:at) returning id"),{"tenant":str(user["tenant_id"]),"ref":ref,"work":str(work_id),"resident":str(user["id"]),"kind":kind,"body":"Resident confirmed work is still ongoing." if body.value else "Resident reported this work may no longer be ongoing.","level":level,"assigned":str(assignee["id"]) if assignee else None,"at":at}).scalar()
    db.execute(text("insert into ticket_event(tenant_id,ticket_id,status,message,is_public,at) values(cast(:tenant as uuid),cast(:id as uuid),'open','Received',false,:at)"),{"tenant":str(user["tenant_id"]),"id":str(ticket),"at":at})
    emit(db,"FeedbackSubmitted.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(work_id),"ticket_id":str(ticket),"ref_no":ref,"resident_id":str(user["id"]),"occurred_at":at.isoformat()})
    no_votes=db.execute(text("select count(*) from feedback_ticket where work_id=cast(:work as uuid) and kind='still_ongoing_no' and created_at>=:since"),{"work":str(work_id),"since":at-timedelta(days=7)}).scalar()
    if no_votes>=3 and work["status"]=="ongoing":
        emit(db,"WorkPossiblyStale.v1",{"tenant_id":str(user["tenant_id"]),"work_id":str(work_id),"occurred_at":at.isoformat(),"reason":"3+ resident reports say work may no longer be ongoing"})
    db.commit()
    return {"ref_no":ref,"value":body.value,"status":"open"}

def escalate_feedback():
    """Escalate unresponded resident tickets once each configured SLA rung is crossed."""
    from app.core.db import SessionLocal
    from app.core.events import emit
    count=0; at=clock.now()
    with SessionLocal() as db:
        rows=db.execute(text("select t.*,w.ward_id,w.agency_id,c.sla_day_ae,c.sla_day_ee,c.sla_day_se,c.sla_time_scale from feedback_ticket t join work w on w.id=t.work_id left join city_config c on c.tenant_id=t.tenant_id where t.kind in ('question','complaint','observation') and t.status not in ('resolved','closed') and t.last_response_at is null and t.current_level<4 and t.escalated_at is distinct from :at order by t.created_at for update of t skip locked"),{"at":at}).mappings().all()
        for ticket in rows:
            elapsed=(at-ticket["created_at"]).total_seconds()/86400
            thresholds=[ticket["sla_day_ae"] or 3,ticket["sla_day_ee"] or 7,ticket["sla_day_se"] or 14]
            threshold_for={2:thresholds[0],3:thresholds[1],4:thresholds[2]}
            scale=float(ticket["sla_time_scale"] or 1)
            target=max([level for level,days in threshold_for.items() if elapsed >= float(days)*scale],default=ticket["current_level"])
            target=min(target,4)
            if target<=ticket["current_level"]: continue
            work={"id":ticket["work_id"],"tenant_id":ticket["tenant_id"],"ward_id":ticket["ward_id"],"agency_id":ticket["agency_id"]}
            assignee=get_assignee(work,target,db)
            db.execute(text("update feedback_ticket set current_level=:level,assigned_to=cast(:assigned as uuid),escalated_at=:at where id=cast(:id as uuid)"),{"level":target,"assigned":str(assignee["id"]) if assignee else None,"at":at,"id":str(ticket["id"])})
            db.execute(text("insert into ticket_event(tenant_id,ticket_id,status,message,is_public,at) values(:tenant,:id,:status,:message,false,:at)"),{"tenant":ticket["tenant_id"],"id":ticket["id"],"status":ticket["status"],"message":f"Escalated to level {target} after SLA elapsed.","at":at})
            if target==4: db.execute(text("update feedback_ticket set overdue_public=true where id=cast(:id as uuid)"),{"id":str(ticket["id"])})
            emit(db,"FeedbackEscalated.v1",{"tenant_id":str(ticket["tenant_id"]),"work_id":str(ticket["work_id"]),"ticket_id":str(ticket["id"]),"ref_no":ticket["ref_no"],"resident_id":str(ticket["resident_id"]),"level":target,"status":ticket["status"],"occurred_at":at.isoformat()})
            count+=1
        db.commit()
    return count
