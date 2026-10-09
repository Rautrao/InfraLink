import json
from collections import defaultdict
from sqlalchemy import text

_subscribers = defaultdict(list)
def subscribe(event_type):
    def register(fn): _subscribers[event_type].append(fn); return fn
    return register

def emit(session, event_type: str, payload: dict):
    event_id = session.execute(text("select nextval(pg_get_serial_sequence('outbox_event','id'))")).scalar()
    payload = {"event_id": event_id, **payload}
    tenant_id = payload.get("tenant_id")
    session.execute(text("insert into outbox_event(id,tenant_id,type,version,payload) values (:id,:tenant,:type,1,cast(:payload as jsonb))"), {"id":event_id,"tenant": tenant_id, "type": event_type, "payload": json.dumps(payload, default=str)})

def dispatch_batch(session, limit=100):
    rows = session.execute(text("select id,type,version,payload from outbox_event where published_at is null order by id limit :limit for update skip locked"), {"limit": limit}).mappings().all()
    for row in rows:
        payload = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
        for handler in _subscribers[row["type"]]: handler({"event_id": row["id"], **payload})
        session.execute(text("update outbox_event set published_at=now() where id=:id"), {"id": row["id"]})
    session.commit()
