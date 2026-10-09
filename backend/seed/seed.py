import json
import uuid
from datetime import timedelta
from sqlalchemy import text
from app.core import clock
from app.core.db import engine
from app.core.security import hash_password

AGENCIES = [
    ("Municipal Roads Dept", "municipal_roads", "ROADS"),
    ("Water & Sewer Board", "water_sewer", "WATER"),
    ("DISCOM Electricity", "electricity", "POWER"),
    ("FibreNet Telecom", "telecom", "FIBRE"),
    ("Metro Rail", "metro", "METRO"),
]
LADDER = ["junior_engineer", "assistant_engineer", "executive_engineer", "superintending_engineer", "chief_engineer", "commissioner"]
REASONS = ["weather", "material_delay", "contractor_delay", "utility_clash", "permit_delay", "funds_delay", "design_change", "public_safety", "court_order", "force_majeure", "other"]

def _reference_data(c, tenant):
    zones=[]; wards=[]
    for index in range(1,5):
        zone=c.execute(text("select id from zone where tenant_id=:t and name=:n"),{"t":tenant,"n":f"Zone {index}"}).scalar()
        if not zone:
            zone=uuid.uuid4()
            c.execute(text("insert into zone(id,tenant_id,name) values (:id,:tenant,:name)"),{"id":zone,"tenant":tenant,"name":f"Zone {index}"})
        zones.append(zone)
        ward=c.execute(text("select id from ward where tenant_id=:t and name=:n"),{"t":tenant,"n":f"Ward {index}"}).scalar()
        if not ward:
            ward=uuid.uuid4()
            c.execute(text("insert into ward(id,tenant_id,zone_id,name) values (:id,:tenant,:zone,:name)"),{"id":ward,"tenant":tenant,"zone":zone,"name":f"Ward {index}"})
        # Adjacent rectangular wards give geometry lookup a clear, deterministic result.
        west=[73.80,73.83,73.8567,73.88][index-1]
        east=[73.83,73.8567,73.88,73.91][index-1]
        c.execute(text("update ward set zone_id=:zone,boundary=ST_Multi(ST_MakeEnvelope(:west,18.48,:east,18.56,4326)) where id=:id"),{"zone":zone,"west":west,"east":east,"id":ward})
        wards.append(ward)
    agency_ids={}
    for name,kind,code in AGENCIES:
        agency_id=c.execute(text("select id from agency where tenant_id=:tenant and short_code=:code"),{"tenant":tenant,"code":code}).scalar()
        if not agency_id:
            agency_id=uuid.uuid4()
            c.execute(text("insert into agency(id,tenant_id,name,type,short_code) values (:id,:tenant,:name,cast(:kind as agency_type),:code)"),{"id":agency_id,"tenant":tenant,"name":name,"kind":kind,"code":code})
        else:
            c.execute(text("update agency set name=:name,type=cast(:kind as agency_type) where id=:id"),{"name":name,"kind":kind,"id":agency_id})
        agency_ids[code]=agency_id
    return zones,wards,agency_ids

def _seed_users(c, tenant, zones, wards, agency_ids):
    user_by_role_ward={}
    staff=[
        ("admin","admin@demo.city",None,None,None),
        ("commissioner","commissioner@demo.city",None,None,None),
        ("chief_engineer","ce.roads@demo.city",None,None,None),
        ("superintending_engineer","se.roads@demo.city",None,zones[0],None),
        ("executive_engineer","ee.roads@demo.city",None,zones[0],None),
        ("assistant_engineer","ae.ward1@demo.city",None,zones[0],wards[0]),
        ("utility_editor","utility.water@demo.city",agency_ids["WATER"],None,None),
        ("contractor","contractor@demo.city",None,None,None),
        ("auditor","auditor@demo.city",None,None,None),
        ("traffic_police","traffic.police@demo.city",None,None,None),
    ]
    for index in range(1,5):
        staff.append(("junior_engineer",f"je.ward{index}@demo.city",None,None,wards[index-1]))
    for role,email,agency_id,zone_id,ward_id in staff:
        user_id=c.execute(text("""
            insert into app_user(tenant_id,agency_id,name,email,password_hash,role,ward_id,zone_id,active)
            values (:tenant,:agency,:name,:email,:password,:role,:ward,:zone,true)
            on conflict(email) do update set tenant_id=excluded.tenant_id,agency_id=excluded.agency_id,name=excluded.name,password_hash=excluded.password_hash,role=excluded.role,ward_id=excluded.ward_id,zone_id=excluded.zone_id,active=true
            returning id
        """),{"tenant":tenant,"agency":agency_id,"name":role.replace("_"," ").title(),"email":email,"password":hash_password("demo1234"),"role":role,"ward":ward_id,"zone":zone_id}).scalar()
        if ward_id: user_by_role_ward[(role,str(ward_id))]=user_id
    residents=[]
    for index in range(1,6):
        phone=f"900000000{index}"
        user_id=c.execute(text("select id from app_user where phone=:phone and role='resident'"),{"phone":phone}).scalar()
        if user_id:
            c.execute(text("update app_user set tenant_id=:tenant,name=:name,ward_id=:ward,active=true where id=:id"),{"tenant":tenant,"name":f"Resident {index}","ward":wards[(index-1)%len(wards)],"id":user_id})
        else:
            user_id=c.execute(text("insert into app_user(tenant_id,name,phone,role,ward_id,active) values (:tenant,:name,:phone,'resident',:ward,true) returning id"),{"tenant":tenant,"name":f"Resident {index}","phone":phone,"ward":wards[(index-1)%len(wards)]}).scalar()
        residents.append(user_id)
    return user_by_role_ward,residents

def _reset_demo(c, tenant):
    # Preserve users, reference geometry, city configuration, and the append-only audit chain.
    for table in ("ticket_event","feedback_ticket","notification","follow_subscription","conflict_decision","conflict_alert","permit","evidence","work_update","work_status_history","work_date_revision","work_milestone"):
        c.execute(text(f"delete from {table} where tenant_id=:tenant"),{"tenant":tenant})
    c.execute(text("delete from work where tenant_id=:tenant"),{"tenant":tenant})
    c.execute(text("delete from outbox_event where tenant_id=:tenant"),{"tenant":tenant})
    c.execute(text("alter sequence work_ref_seq restart with 1"))
    c.execute(text("update city_config set buffer_m=15,lookback_months=24,overdue_days=7,sla_day_ae=3,sla_day_ee=7,sla_day_se=14,sla_time_scale=1,reason_codes=cast(:reasons as jsonb),features='{}'::jsonb where tenant_id=:tenant"),{"tenant":tenant,"reasons":json.dumps(REASONS)})

def _work_specs(today):
    mg_a={"type":"LineString","coordinates":[[73.8350,18.5202],[73.8392,18.5202]]}
    mg_b={"type":"LineString","coordinates":[[73.8354,18.5202],[73.8370,18.5202]]}
    resurfacing={"type":"LineString","coordinates":[[73.8450,18.5202],[73.8492,18.5202]]}
    mg_c={"type":"LineString","coordinates":[[73.8450,18.5202],[73.8492,18.5202]]}
    repeat={"type":"LineString","coordinates":[[73.8660,18.5220],[73.8690,18.5220]]}
    specs=[
        {"title":"MG Road water pipeline trench","purpose":"Replace a leaking main with a planned road restoration","category":"water_pipeline","agency":"WATER","road":"MG Road","ward":2,"geometry":mg_a,"status":"planned","start":today+timedelta(days=5),"end":today+timedelta(days=44),"pct":0},
        {"title":"MG Road fibre duct installation","purpose":"Lay a shared communications duct along the water works corridor","category":"telecom_duct","agency":"FIBRE","road":"MG Road","ward":2,"geometry":mg_b,"status":"planned","start":today+timedelta(days=34),"end":today+timedelta(days=57),"pct":0},
        {"title":"MG Road resurfacing completed","purpose":"Restore the carriageway after utility excavation","category":"resurfacing","agency":"ROADS","road":"MG Road","ward":2,"geometry":resurfacing,"status":"restoration_verified","start":today-timedelta(days=20),"end":today,"pct":100,"resurfaced_on":today},
        {"title":"MG Road electricity duct proposal","purpose":"Install a protected electricity service duct after recent resurfacing","category":"electricity","agency":"POWER","road":"MG Road","ward":2,"geometry":mg_c,"status":"planned","start":today+timedelta(days=78),"end":today+timedelta(days=108),"pct":0},
        {"title":"Baner Road water main renewal","purpose":"Renew a water main with the electricity duct crew working in the same period","category":"water_pipeline","agency":"WATER","road":"Baner Road","ward":3,"geometry":{"type":"LineString","coordinates":[[73.8680,18.5250],[73.8720,18.5250]]},"status":"planned","start":today+timedelta(days=25),"end":today+timedelta(days=62),"pct":0},
        {"title":"Baner Road power cable renewal","purpose":"Replace an underground power cable in the same work window","category":"electricity","agency":"POWER","road":"Baner Road","ward":3,"geometry":{"type":"LineString","coordinates":[[73.8690,18.5250],[73.8715,18.5250]]},"status":"planned","start":today+timedelta(days=52),"end":today+timedelta(days=75),"pct":0},
        {"title":"University Road water cut (completed)","purpose":"Repair the local distribution line","category":"road_cut","agency":"WATER","road":"University Road","ward":3,"geometry":repeat,"status":"completed","start":today-timedelta(days=100),"end":today-timedelta(days=78),"pct":100},
        {"title":"University Road fibre cut proposal","purpose":"Extend the fibre network along the previous trench","category":"telecom_duct","agency":"FIBRE","road":"University Road","ward":3,"geometry":repeat,"status":"planned","start":today+timedelta(days=35),"end":today+timedelta(days=52),"pct":0},
    ]
    statuses=["permitted","ongoing","paused","completed","restoration_verified","planned","ongoing","permitted","completed"]
    categories=["drainage","sewer","electricity","footpath","metro","road_cut","water_pipeline","telecom_duct","resurfacing","other"]
    roads=["FC Road","JM Road","Karve Road","Paud Road","Aundh Road","Koregaon Park Road","Senapati Bapat Road"]
    for index in range(8,35):
        status=statuses[(index-8)%len(statuses)]
        ward_num=(index%4)+1
        west=[73.80,73.83,73.8567,73.88][ward_num-1]
        lng=west+0.007+(index%3)*0.002
        lat=18.496+(index%12)*0.004
        geometry={"type":"LineString","coordinates":[[lng,lat],[lng+0.0015,lat+0.0005]]}
        delayed=index in (10,17,26)
        if delayed:
            start=today-timedelta(days=50+index)
            end=today-timedelta(days=3+index%4)
        elif status in ("completed","restoration_verified"):
            start=today-timedelta(days=60+index); end=today-timedelta(days=35+index)
        else:
            start=today+timedelta(days=(index%18)-5); end=today+timedelta(days=25+index%24)
        pct=100 if status in ("completed","restoration_verified") else (0 if status=="planned" else min(20+index,85))
        specs.append({"title":f"{roads[index%len(roads)]} {categories[index%len(categories)].replace('_',' ')} work {index+1:02d}","purpose":"Maintain essential public infrastructure and restore the work area safely.","category":categories[index%len(categories)],"agency":["ROADS","WATER","POWER","FIBRE","METRO"][index%5],"road":roads[index%len(roads)],"ward":ward_num,"geometry":geometry,"status":status,"start":start,"end":end,"pct":pct,"delayed":delayed})
    return specs

def _insert_works(c, tenant, agency_ids, wards, user_by_role_ward, today):
    specs=_work_specs(today)
    for index,spec in enumerate(specs,1):
        ref=f"WRK-{today.year}-{index:05d}"
        exists=c.execute(text("select id from work where ref_no=:ref"),{"ref":ref}).scalar()
        if exists: continue
        ward_id=wards[spec["ward"]-1]
        engineer=user_by_role_ward.get(("junior_engineer",str(ward_id)))
        actual_start=spec["start"] if spec["status"] in ("ongoing","paused","completed","restoration_verified") else None
        actual_end=spec["end"] if spec["status"] in ("completed","restoration_verified") else None
        original=spec["end"]-timedelta(days=7) if spec.get("delayed") else spec["end"]
        public_flags={"seeded":True}
        work_id=c.execute(text("""
            insert into work(tenant_id,ref_no,title,purpose,category,status,agency_id,contractor_name,contractor_public,contact_name,contact_phone,contact_email,contact_channel,road_name,ward_id,geometry,length_m,planned_start,original_target_end,current_target_end,actual_start,actual_end,pct_complete,disruption_type,disruption_note,is_public,public_flags,resurfaced_on,last_update_at,restoration_verified_at,created_by)
            values (:tenant,:ref,:title,:purpose,cast(:category as work_category),cast(:status as work_status),:agency,'Demo City Civil Works',true,'Project Site Office','+91 98765 40001','works@demo.city','office',:road,:ward,ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326),ST_Length(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)::geography),:start,:original,:end,:actual_start,:actual_end,:pct,'none',null,true,cast(:flags as jsonb),:resurfaced,:updated,:restored,:creator)
            returning id
        """),{"tenant":tenant,"ref":ref,"title":spec["title"],"purpose":spec["purpose"],"category":spec["category"],"status":spec["status"],"agency":agency_ids[spec["agency"]],"road":spec["road"],"ward":ward_id,"geometry":json.dumps(spec["geometry"]),"start":spec["start"],"original":original,"end":spec["end"],"actual_start":actual_start,"actual_end":actual_end,"pct":spec["pct"],"flags":json.dumps(public_flags),"resurfaced":spec.get("resurfaced_on"),"updated":clock.now()-timedelta(days=20 if index in (9,24) else index%6),"restored":clock.now() if spec["status"]=="restoration_verified" else None,"creator":engineer}).scalar()
        if spec.get("delayed"):
            c.execute(text("insert into work_date_revision(tenant_id,work_id,old_target,new_target,reason_code,explanation,by_user,at) values (:tenant,:work,:old,:new,'material_delay','Supplier delivery was later than the confirmed shipment date.',:user,:at)"),{"tenant":tenant,"work":work_id,"old":original,"new":spec["end"],"user":engineer,"at":clock.now()-timedelta(days=8)})
        c.execute(text("insert into work_status_history(tenant_id,work_id,from_status,to_status,reason_code,explanation,by_user,at) values (:tenant,:work,null,cast(:status as work_status),null,'Initial seeded status',:user,:at)"),{"tenant":tenant,"work":work_id,"status":spec["status"],"user":engineer,"at":clock.now()-timedelta(days=index)})
        if index in (3,7,12,21) and spec["status"] in ("completed","restoration_verified"):
            c.execute(text("insert into evidence(tenant_id,work_id,file_path,public_path,taken_at,exif_ok,uploaded_by,verified_by,verified_at,kind) values (:tenant,:work,:path,:public,:taken,true,:user,:user,:verified,'restoration')"),{"tenant":tenant,"work":work_id,"path":f"seed/{ref}-restoration.jpg","public":f"/files/{ref}-restoration.jpg","taken":clock.now()-timedelta(days=4),"user":engineer,"verified":clock.now()-timedelta(days=2)})
        if index<=12:
            c.execute(text("insert into work_milestone(tenant_id,work_id,name,planned_date,actual_date,pct,sort) values (:tenant,:work,'Service installation',:planned,:actual,:pct,1)"),{"tenant":tenant,"work":work_id,"planned":spec["start"]+timedelta(days=5),"actual":spec["start"]+timedelta(days=5) if spec["pct"]==100 else None,"pct":spec["pct"],})
        if index in (9,24):
            c.execute(text("insert into work_update(tenant_id,work_id,text,pct_complete,by_user,at,is_public) values (:tenant,:work,'Field update recorded before the current reporting window.',:pct,:user,:at,true)"),{"tenant":tenant,"work":work_id,"pct":spec["pct"],"user":engineer,"at":clock.now()-timedelta(days=20)})
    c.execute(text("select setval('work_ref_seq',greatest((select coalesce(max(split_part(ref_no,'-',3)::bigint),0) from work where tenant_id=:tenant and ref_no like :prefix),(select last_value from work_ref_seq)),true)"),{"tenant":tenant,"prefix":f"WRK-{today.year}-%"})
    return c.execute(text("select id,ref_no,ward_id,agency_id from work where tenant_id=:tenant order by ref_no"),{"tenant":tenant}).mappings().all()

def _insert_feedback(c, tenant, works, residents, user_by_role_ward, today):
    statuses=["open","open","acknowledged","in_progress","open","open","resolved","open","acknowledged","open","in_progress","open","open","resolved","open"]
    levels=[1,1,1,2,2,3,1,3,2,4,2,1,3,1,4]
    ages=[0,1,2,4,5,8,10,15,3,7,9,12,16,20,21]
    for index in range(15):
        ref=f"FB-{today.year}-{index+1:06d}"
        exists=c.execute(text("select 1 from feedback_ticket where ref_no=:ref"),{"ref":ref}).scalar()
        if exists: continue
        work=works[index%len(works)]
        resident=residents[index%len(residents)]
        ward=str(work["ward_id"])
        assigned=user_by_role_ward.get(("junior_engineer",ward))
        if levels[index]>1:
            rung=min(levels[index],len(LADDER))
            role=LADDER[rung-1]
            assigned=c.execute(text("select id from app_user where tenant_id=:tenant and role=:role and active order by (ward_id=cast(:ward as uuid)) desc limit 1"),{"tenant":tenant,"role":role,"ward":ward}).scalar() or assigned
        created=clock.now()-timedelta(days=ages[index])
        ticket=c.execute(text("""
            insert into feedback_ticket(tenant_id,ref_no,work_id,resident_id,kind,text,status,current_level,assigned_to,is_public,moderation,created_at,last_response_at,escalated_at)
            values (:tenant,:ref,:work,:resident,:kind,:message,cast(:status as feedback_status),:level,:assigned,false,'pending',:created,:response,:escalated)
            returning id
        """),{"tenant":tenant,"ref":ref,"work":work["id"],"resident":resident,"kind":"complaint" if index%3==1 else "observation","message":f"Seeded resident feedback item {index+1} about the public work schedule and disruption.","status":statuses[index],"level":levels[index],"assigned":assigned,"created":created,"response":created+timedelta(days=1) if statuses[index] in ("acknowledged","in_progress","resolved") else None,"escalated":created+timedelta(days=3) if levels[index]>1 else None}).scalar()
        c.execute(text("insert into ticket_event(tenant_id,ticket_id,status,responder_id,message,is_public,at) values (:tenant,:ticket,cast(:status as feedback_status),null,'Received',false,:at)"),{"tenant":tenant,"ticket":ticket,"status":statuses[index],"at":created})

def main(reset=False):
    today=clock.today()
    with engine.begin() as c:
        c.execute(text("create sequence if not exists work_ref_seq"))
        tenant=c.execute(text("select id from tenant where slug='demo-city'")).scalar()
        if not tenant:
            tenant=uuid.uuid4()
            c.execute(text("insert into tenant(id,name,slug,center) values (:id,'Demo City','demo-city',ST_SetSRID(ST_MakePoint(73.8567,18.5204),4326))"),{"id":tenant})
        zones,wards,agency_ids=_reference_data(c,tenant)
        c.execute(text("insert into city_config(tenant_id) values (:tenant) on conflict do nothing"),{"tenant":tenant})
        if reset: _reset_demo(c,tenant)
        user_by_role_ward,residents=_seed_users(c,tenant,zones,wards,agency_ids)
        for level,role in enumerate(LADDER,1):
            c.execute(text("insert into escalation_level(tenant_id,agency_id,level,role) select :tenant,null,:level,:role where not exists(select 1 from escalation_level where tenant_id=:tenant and agency_id is null and level=:level)"),{"tenant":tenant,"level":level,"role":role})
        works=_insert_works(c,tenant,agency_ids,wards,user_by_role_ward,today)
        _insert_feedback(c,tenant,works,residents,user_by_role_ward,today)
    print("Seeded Demo City: 4 wards, 5 agencies, 35+ works, and 15 feedback tickets.")

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--reset",action="store_true")
    main(reset=parser.parse_args().reset)
