import uuid
from sqlalchemy import text
from app.core.db import engine
from app.core.security import hash_password

ROLES = ["admin","commissioner","chief_engineer","superintending_engineer","executive_engineer","assistant_engineer","junior_engineer","utility_editor","contractor","auditor","traffic_police","resident"]
AGENCIES = [("Municipal Roads Dept","municipal_roads","ROADS"),("Water & Sewer Board","water_sewer","WATER"),("DISCOM Electricity","electricity","POWER"),("FibreNet Telecom","telecom","FIBRE"),("Metro Rail","metro","METRO")]

def main():
    with engine.begin() as c:
        tenant = c.execute(text("select id from tenant where slug='demo-city'")).scalar()
        if not tenant:
            tenant = uuid.uuid4()
            c.execute(text("insert into tenant(id,name,slug,center) values (:id,'Demo City','demo-city',ST_SetSRID(ST_MakePoint(73.8567,18.5204),4326))"), {"id":tenant})
        zone_ids=[]; ward_ids=[]
        for i in range(1,5):
            zone=c.execute(text("select id from zone where tenant_id=:t and name=:n"),{"t":tenant,"n":f"Zone {i}"}).scalar()
            if not zone:
                zone=uuid.uuid4(); c.execute(text("insert into zone(id,tenant_id,name) values (:id,:t,:n)"),{"id":zone,"t":tenant,"n":f"Zone {i}"})
            zone_ids.append(zone)
            ward=c.execute(text("select id from ward where tenant_id=:t and name=:n"),{"t":tenant,"n":f"Ward {i}"}).scalar()
            if not ward:
                ward=uuid.uuid4(); dx=(i-2.5)*.01
                c.execute(text("insert into ward(id,tenant_id,zone_id,name,boundary) values (:id,:t,:z,:n,ST_Multi(ST_MakeEnvelope(73.83+:dx,18.49,73.88+:dx,18.55,4326)))"),{"id":ward,"t":tenant,"z":zone,"n":f"Ward {i}","dx":dx})
            ward_ids.append(ward)
        agency_ids=[]
        for name,typ,code in AGENCIES:
            aid=c.execute(text("select id from agency where tenant_id=:t and short_code=:s"),{"t":tenant,"s":code}).scalar()
            if not aid:
                aid=uuid.uuid4(); c.execute(text("insert into agency(id,tenant_id,name,type,short_code) values (:id,:t,:n,:type,:s)"),{"id":aid,"t":tenant,"n":name,"type":typ,"s":code})
            agency_ids.append(aid)
        for i,role in enumerate(ROLES):
            email=f"{role}.demo@demo.city"
            if role=="junior_engineer": email="je.ward1@demo.city"
            if role=="executive_engineer": email="ee.roads@demo.city"
            if role=="utility_editor": email="utility.water@demo.city"
            if role=="auditor": email="auditor@demo.city"
            if role=="admin": email="admin@demo.city"
            phone=f"900000000{i-6}" if role=="resident" else None
            if role=="resident":
                for n in range(1,6):
                    c.execute(text("insert into app_user(tenant_id,name,phone,role,ward_id,active) select :t,:name,:phone,'resident',:ward,true where not exists(select 1 from app_user where phone=:phone)"),{"t":tenant,"name":f"Resident {n}","phone":f"900000000{n}","ward":ward_ids[(n-1)%4]})
                continue
            c.execute(text("insert into app_user(tenant_id,agency_id,name,email,password_hash,role,ward_id,zone_id,active) select :t,:a,:name,:email,:hash,:role,:ward,:zone,true where not exists(select 1 from app_user where email=:email)"),{"t":tenant,"a":agency_ids[1 if role=="utility_editor" else 0],"name":role.replace('_',' ').title(),"email":email,"hash":hash_password("demo1234"),"role":role,"ward":ward_ids[0] if role=="junior_engineer" else None,"zone":zone_ids[0] if role in ("executive_engineer","superintending_engineer") else None})
        c.execute(text("insert into city_config(tenant_id) values (:t) on conflict do nothing"),{"t":tenant})
        for level,r in enumerate(["junior_engineer","assistant_engineer","executive_engineer","superintending_engineer","chief_engineer","commissioner"],1):
            c.execute(text("insert into escalation_level(tenant_id,level,role) select :t,:l,:r where not exists(select 1 from escalation_level where tenant_id=:t and agency_id is null and level=:l)"),{"t":tenant,"l":level,"r":r})
    print("Seeded Demo City reference data and demo accounts.")

if __name__ == "__main__": main()
