import hashlib, json
from sqlalchemy import text
from app.core.clock import now

def write_audit(session, actor, action, entity, entity_id, before=None, after=None):
    tenant_id = actor.get("tenant_id") if actor else None
    previous = session.execute(text("select hash from audit_log where tenant_id=:tenant order by id desc limit 1"), {"tenant": tenant_id}).scalar()
    previous = previous or "0" * 64
    body = {"tenant_id": str(tenant_id), "actor_id": str(actor["id"]) if actor else None, "action": action, "entity": entity, "entity_id": str(entity_id) if entity_id is not None else None, "before": before, "after": after, "at": now().isoformat()}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256((previous + canonical).encode()).hexdigest()
    session.execute(text("insert into audit_log(tenant_id,actor_id,action,entity,entity_id,before,after,at,prev_hash,hash) values (:tenant,:actor,:action,:entity,:entity_id,cast(:before as jsonb),cast(:after as jsonb),:at,:prev,:hash)"), {"tenant": tenant_id, "actor": actor.get("id") if actor else None, "action": action, "entity": entity, "entity_id": entity_id, "before": json.dumps(before, default=str) if before is not None else None, "after": json.dumps(after, default=str) if after is not None else None, "at": now(), "prev": previous, "hash": digest})
