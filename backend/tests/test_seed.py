from sqlalchemy import text
from app.core.db import SessionLocal
from app.core.clock import today
from seed.seed import main as seed_demo_city

def test_demo_seed_has_required_examples_and_remains_idempotent(client):
    with SessionLocal() as session:
        seeded_before=session.execute(text("select count(*) from work where public_flags->>'seeded'='true'")).scalar()
        feedback_before=session.execute(text("select count(*) from feedback_ticket where ref_no like :prefix"),{"prefix":f"FB-{today().year}-%"}).scalar()
        assert seeded_before==35
        assert feedback_before==15
        statuses=set(session.execute(text("select distinct status::text from work where public_flags->>'seeded'='true'")).scalars())
        assert {"planned","permitted","ongoing","paused","completed","restoration_verified"}.issubset(statuses)
        delayed=session.execute(text("select count(*) from work where public_flags->>'seeded'='true' and current_target_end<:today and status::text not in ('completed','restoration_verified','closed')"),{"today":today()}).scalar()
        overdue=session.execute(text("select count(*) from work w left join city_config c on c.tenant_id=w.tenant_id where w.public_flags->>'seeded'='true' and w.status::text in ('ongoing','permitted','paused') and w.last_update_at<now()-make_interval(days=>coalesce(c.overdue_days,7))")).scalar()
        assert delayed==3 and overdue==2
        dates=session.execute(text("""
            select x.planned_start,x.current_target_end,y.planned_start,y.current_target_end
            from work x join work y on y.tenant_id=x.tenant_id
            where x.ref_no=:a and y.ref_no=:b
        """),{"a":f"WRK-{today().year}-00001","b":f"WRK-{today().year}-00002"}).one()
        overlap=(min(dates[1],dates[3])-max(dates[0],dates[2])).days+1
        assert overlap==11
        second=session.execute(text("select x.planned_start,x.current_target_end,y.planned_start,y.current_target_end from work x join work y on y.tenant_id=x.tenant_id where x.ref_no=:a and y.ref_no=:b"),{"a":f"WRK-{today().year}-00005","b":f"WRK-{today().year}-00006"}).one()
        assert (min(second[1],second[3])-max(second[0],second[2])).days+1==11
        repeat=session.execute(text("select ST_DWithin(x.geometry::geography,y.geometry::geography,15) from work x join work y on y.tenant_id=x.tenant_id where x.ref_no=:a and y.ref_no=:b"),{"a":f"WRK-{today().year}-00007","b":f"WRK-{today().year}-00008"}).scalar()
        assert repeat is True
        resurfaced=session.execute(text("select resurfaced_on from work where ref_no=:ref"),{"ref":f"WRK-{today().year}-00003"}).scalar()
        proposed=session.execute(text("select planned_start from work where ref_no=:ref"),{"ref":f"WRK-{today().year}-00004"}).scalar()
        assert (proposed-resurfaced).days==78
    seed_demo_city()
    with SessionLocal() as session:
        seeded_after=session.execute(text("select count(*) from work where public_flags->>'seeded'='true'")).scalar()
        feedback_after=session.execute(text("select count(*) from feedback_ticket where ref_no like :prefix"),{"prefix":f"FB-{today().year}-%"}).scalar()
    assert seeded_after==seeded_before and feedback_after==feedback_before
