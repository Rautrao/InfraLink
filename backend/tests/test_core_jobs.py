import json
from datetime import timedelta
from sqlalchemy import text
from conftest import login
from test_project_registry import create_work
from app.core.clock import now
from app.core.db import engine
from app.core.jobs import check_overdue_updates

def test_overdue_job_emits_once_per_work_and_week(client):
    token=login(client,"je.ward1@demo.city")
    work=create_work(client,token,"Overdue job work").json()
    with engine.begin() as conn:
        conn.execute(text("update work set status='ongoing',last_update_at=:old,public_flags='{}'::jsonb where id=cast(:id as uuid)"),{"old":now()-timedelta(days=30),"id":work["id"]})
    assert check_overdue_updates() >= 1
    with engine.begin() as conn:
        rows=conn.execute(text("select id,payload from outbox_event where type='UpdateOverdue.v1' and payload->>'work_id'=:work order by id"),{"work":work["id"]}).mappings().all()
    assert len(rows)==1
    payload=rows[0]["payload"] if isinstance(rows[0]["payload"],dict) else json.loads(rows[0]["payload"])
    assert payload["event_id"]==rows[0]["id"] and payload["actor_id"] is None and payload["occurred_at"]
    assert check_overdue_updates()==0
    with engine.begin() as conn:
        count=conn.execute(text("select count(*) from outbox_event where type='UpdateOverdue.v1' and payload->>'work_id'=:work"),{"work":work["id"]}).scalar()
    assert count==1
