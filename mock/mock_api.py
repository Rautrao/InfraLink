from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app=FastAPI(title="Public Works Mock API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
works=[]
for i in range(1,11):
    lat=18.510+(i%5)*.004; lng=73.842+(i%4)*.004
    works.append({"id":f"demo-work-{i}","ref_no":f"WRK-2026-{i:05d}","title":["MG Road water pipeline renewal","FC Road resurfacing","Ward drain improvement","Fibre duct installation"][i%4],"purpose":"Improve essential public infrastructure with planned, coordinated work.","category":["water_pipeline","resurfacing","drainage","telecom_duct"][i%4],"status":["ongoing","planned","permitted","completed"][i%4],"delayed":i in (3,8),"update_overdue":i==6,"agency":{"id":f"agency-{i%5+1}","name":["Municipal Roads Dept","Water & Sewer Board","DISCOM Electricity","FibreNet Telecom","Metro Rail"][i%5]},"contractor_name":"Pune Infrastructure Works","contact":{"name":"Site Engineer","phone_masked":"+91 ******0001","email":None,"channel":"office"},"road_name":["Mahatma Gandhi Road","Fergusson College Road","JM Road","Baner Road"][i%4],"ward":{"id":f"ward-{i%4+1}","name":f"Ward {i%4+1}"},"geometry":{"type":"LineString","coordinates":[[lng,lat],[lng+.002,lat+.001]]},"length_m":240+i*35,"planned_start":"2026-10-01","original_target_end":"2026-11-01","current_target_end":"2026-11-01","pct_complete":min(i*9,100),"disruption":{"type":"partial_closure" if i%3==0 else "none","note":"Use the signed diversion." if i%3==0 else None},"last_update_at":"2026-10-09T08:30:00Z","date_revisions":[],"milestones":[],"updates":[],"evidence":[],"permits":[],"nearby_notices":[],"still_ongoing":{"yes":0,"no":0,"last_confirmed_at":None}})

@app.get("/works")
def list_works(page:int=1,page_size:int=20,ward_id:str|None=None,status:str|None=None,q:str|None=None):
    rows=[w for w in works if (not ward_id or w["ward"]["id"]==ward_id) and (not status or w["status"]==status) and (not q or q.lower() in w["title"].lower() or q.lower() in w["road_name"].lower())]
    return {"items":rows[(page-1)*page_size:page*page_size],"total":len(rows),"page":page,"page_size":page_size}

@app.get("/works/geojson")
def works_geojson():
    return {"type":"FeatureCollection","features":[{"type":"Feature","id":w["id"],"geometry":w["geometry"],"properties":{k:w[k] for k in ("id","ref_no","title","status","delayed","category","last_update_at")}|{"agency":w["agency"]["name"]}} for w in works]}

@app.get("/works/{work_id}")
def work_detail(work_id:str):
    work=next((w for w in works if w["id"]==work_id),None)
    if work is None: raise HTTPException(404,"Work not found")
    return work

@app.get("/works/{work_id}/feedback/public")
def public_feedback(work_id:str): return {"items":[],"total":0}

@app.get("/reports/summary")
def summary():
    return {"by_status":{"ongoing":3,"planned":3,"permitted":2,"completed":2},"by_ward":[{"ward":"Ward 1","count":3},{"ward":"Ward 2","count":3}],"by_agency":[],"delayed_count":2,"overdue_updates_count":1,"open_conflicts":2,"repeat_dig_segments":1,"feedback":{"open":4,"overdue":1}}
