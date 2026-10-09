from app.core import clock
from app.core.db import SessionLocal
from app.core.events import emit
from sqlalchemy import text

def check_overdue_updates():
    """Flag newly overdue active works once per ISO week and enqueue events."""
    now=clock.now()
    week_key=f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    count=0
    with SessionLocal() as session:
        rows=session.execute(text("""
            select w.id,w.tenant_id,w.ref_no,w.title,w.road_name,w.ward_id,w.public_flags
            from work w left join city_config cc on cc.tenant_id=w.tenant_id
            where w.status::text in ('ongoing','permitted','paused')
              and (w.last_update_at is null or w.last_update_at < :now - make_interval(days=>coalesce(cc.overdue_days,7)))
              and coalesce(w.public_flags->>'update_overdue_week','') <> :week
            order by w.id for update of w skip locked
        """),{"now":now,"week":week_key}).mappings().all()
        for row in rows:
            session.execute(text("update work set public_flags=jsonb_set(coalesce(public_flags,'{}'::jsonb),'{update_overdue_week}',to_jsonb(cast(:week as text)),true) where id=:id"),{"week":week_key,"id":row["id"]})
            emit(session,"UpdateOverdue.v1",{"tenant_id":str(row["tenant_id"]),"work_id":str(row["id"]),"actor_id":None,"occurred_at":now.isoformat(),"ref_no":row["ref_no"],"title":row["title"],"road_name":row["road_name"]})
            count+=1
        session.commit()
    return count
