import os
import smtplib
from email.message import EmailMessage
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import text

from app.core import clock
from app.core.db import get_db, SessionLocal
from app.core.events import subscribe
from app.core.security import require_roles

router=APIRouter()
RESIDENT=("resident",)

class FollowBody(BaseModel):
    work_id: UUID | None=None
    ward_id: UUID | None=None
    channel: str="console"
    @model_validator(mode="after")
    def one_target(self):
        if (self.work_id is None)==(self.ward_id is None): raise ValueError("Provide exactly one of work_id or ward_id")
        if self.channel not in ("sms","whatsapp","email","push","console"): raise ValueError("Invalid follow channel")
        return self

def _deliver(db, event_type, payload):
    work_id=payload.get("work_id")
    if not work_id: return 0
    work=db.execute(text("select w.id,w.tenant_id,w.title,w.road_name,w.ward_id,wd.name ward_name,w.planned_start,w.status::text status,w.pct_complete from work w left join ward wd on wd.id=w.ward_id where w.id=cast(:id as uuid)"),{"id":str(work_id)}).mappings().first()
    if not work: return 0
    changed=payload.get("changed_fields",[])
    if event_type=="WorkUpdated.v1" and changed:
        meaningful=set(changed)-{"last_update_at","text","description","title","purpose","disruption_note"}
        if meaningful=={"pct_complete"} and abs(int(payload.get("pct_delta",0)))<10: return 0
        if not meaningful: return 0
    critical=event_type in ("WorkStatusChanged.v1","WorkDatesRevised.v1","PermitSubmitted.v1","PermitApproved.v1","PermitHeld.v1","ConflictDetected.v1","ConflictResolved.v1","FeedbackResponded.v1","FeedbackEscalated.v1","RestorationVerified.v1")
    kind=event_type.removesuffix(".v1").lower()
    title=_title(event_type,work)
    body=f"{work['title']} · {work['road_name'] or 'Road/location pending'}, {work['ward_name'] or 'Ward pending'}. {title}."
    link=f"/works/{work_id}"
    subscribers=db.execute(text("select fs.resident_id,fs.channel,u.email,u.phone from follow_subscription fs join app_user u on u.id=fs.resident_id where fs.tenant_id=cast(:tenant as uuid) and fs.active and (fs.work_id=cast(:work as uuid) or fs.ward_id=cast(:ward as uuid))"),{"tenant":str(work["tenant_id"]),"work":str(work_id),"ward":str(work["ward_id"]) if work["ward_id"] else "00000000-0000-0000-0000-000000000000"}).mappings().all()
    for subscriber in subscribers:
        day=clock.today().isoformat()
        dedupe=f"{subscriber['resident_id']}:{work_id}:{kind}:{payload.get('event_id') or payload.get('occurred_at') or day}"
        if not critical: dedupe=f"digest:{subscriber['resident_id']}:{day}"
        if not critical:
            existing=db.execute(text("select id,body from notification where tenant_id=cast(:tenant as uuid) and dedupe_key=:key"),{"tenant":str(work["tenant_id"]),"key":dedupe}).mappings().first()
            if existing:
                db.execute(text("update notification set body=case when position(:title in body)>0 then body else body||E'\\n• '||:body end where id=:id"),{"title":title,"body":body,"id":str(existing["id"])})
                continue
        inserted=db.execute(text("insert into notification(tenant_id,user_id,work_id,kind,title,body,link,channel,status,dedupe_key,created_at) values(cast(:tenant as uuid),cast(:user as uuid),cast(:work as uuid),:kind,:title,:body,:link,cast(:channel as follow_channel),'queued',:dedupe,:at) on conflict(tenant_id,dedupe_key) do nothing returning id"),{"tenant":str(work["tenant_id"]),"user":str(subscriber["resident_id"]),"work":str(work_id),"kind":"daily_digest" if not critical else kind,"title":"Your daily works digest" if not critical else title,"body":body,"link":link,"channel":subscriber["channel"],"dedupe":dedupe,"at":clock.now()}).scalar()
        if inserted: _adapter(subscriber,subscriber["channel"],title,body)
    return len(subscribers)

def _title(event_type,work):
    return {"WorkCreated.v1":"A new work was registered.","WorkUpdated.v1":"A work update was posted.","WorkStartingTomorrow.v1":"This work is starting tomorrow.","WorkStatusChanged.v1":f"Status changed to {work['status']}.","PermitApproved.v1":"A permit was approved.","ConflictResolved.v1":"Nearby works were coordinated.","FeedbackResponded.v1":"A staff member responded to resident feedback.","FeedbackEscalated.v1":"Your feedback was escalated for attention.","UpdateOverdue.v1":"This work has not had a recent update."}.get(event_type,"There is a new update.")

def _adapter(user,channel,title,body):
    if channel=="console":
        print(f"[ConsoleAdapter] {user['resident_id']}: {title} — {body}",flush=True);return
    if channel=="email":
        host=os.getenv("SMTP_HOST"); recipient=user.get("email")
        if not host or not recipient:
            print(f"[EmailAdapter stub] {recipient or 'missing email'}: {title} — {body}",flush=True);return
        message=EmailMessage(); message["Subject"]=title; message["From"]=os.getenv("SMTP_FROM","notifications@publicworks.local");message["To"]=recipient;message.set_content(body)
        with smtplib.SMTP(host,int(os.getenv("SMTP_PORT","25")),timeout=5) as smtp:
            if os.getenv("SMTP_STARTTLS","false").lower() in ("1","true","yes"):smtp.starttls()
            username=os.getenv("SMTP_USER");password=os.getenv("SMTP_PASSWORD")
            if username and password:smtp.login(username,password)
            smtp.send_message(message)
        return
    if channel in ("sms","whatsapp"):
        print(f"[{channel.title()}Adapter] DLT template id: {os.getenv('DLT_TEMPLATE_ID','DEMO-TEMPLATE')}; {user.get('phone') or 'missing phone'}: {title}",flush=True)
        return
    print(f"[{channel}Adapter stub] {title} — {body}",flush=True)

def _handler(event_type):
    @subscribe(event_type)
    def handle(payload):
        with SessionLocal() as db:
            try: _deliver(db,event_type,payload);db.commit()
            except Exception: db.rollback();raise
    return handle

for _event in ("WorkCreated.v1","WorkUpdated.v1","WorkStatusChanged.v1","WorkDatesRevised.v1","PermitSubmitted.v1","PermitApproved.v1","PermitHeld.v1","ConflictDetected.v1","ConflictResolved.v1","FeedbackResponded.v1","FeedbackEscalated.v1","RestorationVerified.v1","EvidenceAdded.v1","UpdateOverdue.v1"):
    _handler(_event)

@router.post("/follows",status_code=201)
def follow(body:FollowBody,db=Depends(get_db),user=Depends(require_roles(*RESIDENT))):
    if body.work_id:
        exists=db.execute(text("select 1 from work where id=cast(:id as uuid) and tenant_id=cast(:tenant as uuid) and is_public"),{"id":str(body.work_id),"tenant":str(user["tenant_id"])}).scalar()
        if not exists: raise HTTPException(404,"Public work not found")
    else:
        exists=db.execute(text("select 1 from ward where id=cast(:id as uuid) and tenant_id=cast(:tenant as uuid)"),{"id":str(body.ward_id),"tenant":str(user["tenant_id"])}).scalar()
        if not exists: raise HTTPException(404,"Ward not found")
    params={"tenant":str(user["tenant_id"]),"resident":str(user["id"]),"work":str(body.work_id) if body.work_id else None,"ward":str(body.ward_id) if body.ward_id else None,"channel":body.channel}
    existing=db.execute(text("select id from follow_subscription where tenant_id=cast(:tenant as uuid) and resident_id=cast(:resident as uuid) and work_id is not distinct from cast(:work as uuid) and ward_id is not distinct from cast(:ward as uuid) and channel=cast(:channel as follow_channel) and active limit 1"),params).scalar()
    row=existing or db.execute(text("insert into follow_subscription(tenant_id,resident_id,work_id,ward_id,channel,active) values(cast(:tenant as uuid),cast(:resident as uuid),cast(:work as uuid),cast(:ward as uuid),cast(:channel as follow_channel),true) returning id"),params).scalar()
    db.commit();return {"id":str(row),"work_id":params["work"],"ward_id":params["ward"],"channel":body.channel,"active":True}

@router.get("/follows")
def follows(db=Depends(get_db),user=Depends(require_roles(*RESIDENT))):
    rows=db.execute(text("select fs.id,fs.work_id,fs.ward_id,fs.channel,fs.active,w.title work_title,wd.name ward_name from follow_subscription fs left join work w on w.id=fs.work_id left join ward wd on wd.id=fs.ward_id where fs.resident_id=cast(:user as uuid) and fs.tenant_id=cast(:tenant as uuid) and fs.active order by fs.id"),{"user":str(user["id"]),"tenant":str(user["tenant_id"])}).mappings().all()
    return {"items":[{**dict(r),"id":str(r["id"]),"work_id":str(r["work_id"]) if r["work_id"] else None,"ward_id":str(r["ward_id"]) if r["ward_id"] else None} for r in rows]}

@router.delete("/follows")
def unfollow(work_id:UUID|None=None,ward_id:UUID|None=None,db=Depends(get_db),user=Depends(require_roles(*RESIDENT))):
    if (work_id is None)==(ward_id is None): raise HTTPException(422,"Provide exactly one of work_id or ward_id")
    clause="work_id=cast(:target as uuid)" if work_id else "ward_id=cast(:target as uuid)"
    result=db.execute(text(f"update follow_subscription set active=false where resident_id=cast(:user as uuid) and tenant_id=cast(:tenant as uuid) and {clause} and active"),{"user":str(user["id"]),"tenant":str(user["tenant_id"]),"target":str(work_id or ward_id)})
    db.commit();return {"unfollowed":result.rowcount>0}

@router.get("/notifications/mine")
def mine(db=Depends(get_db),user=Depends(require_roles(*RESIDENT))):
    rows=db.execute(text("select n.*,w.title project_name,w.road_name,wd.name ward_name from notification n left join work w on w.id=n.work_id left join ward wd on wd.id=w.ward_id where n.user_id=cast(:user as uuid) and n.tenant_id=cast(:tenant as uuid) order by n.created_at desc"),{"user":str(user["id"]),"tenant":str(user["tenant_id"])}).mappings().all()
    return {"items":[{**dict(r),"id":str(r["id"]),"work_id":str(r["work_id"]) if r["work_id"] else None,"project_name":r["project_name"],"affected_location":{"road_name":r["road_name"],"ward":r["ward_name"]}} for r in rows]}

@router.patch("/notifications/{notification_id}/read")
def mark_read(notification_id:UUID,db=Depends(get_db),user=Depends(require_roles(*RESIDENT))):
    row=db.execute(text("update notification set read_at=coalesce(read_at,:at) where id=cast(:id as uuid) and user_id=cast(:user as uuid) and tenant_id=cast(:tenant as uuid) returning id,read_at"),{"id":str(notification_id),"user":str(user["id"]),"tenant":str(user["tenant_id"]),"at":clock.now()}).mappings().first()
    if not row: raise HTTPException(404,"Notification not found")
    db.commit();return {"id":str(row["id"]),"read":True}

def notify_starting_tomorrow():
    with SessionLocal() as db:
        tomorrow=clock.today()+timedelta(days=1)
        rows=db.execute(text("select w.id from work w where w.is_public and w.planned_start=:tomorrow and w.status='planned'"),{"tomorrow":tomorrow}).scalars().all()
        count=0
        for wid in rows: count+=_deliver(db,"WorkStartingTomorrow.v1",{"work_id":str(wid),"occurred_at":clock.now().isoformat()})
        db.commit();return count
