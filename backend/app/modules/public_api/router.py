import csv
from datetime import timezone
from email.utils import format_datetime
from io import StringIO
from time import monotonic
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.core import clock
from app.core.db import get_db

router=APIRouter()
_cache={}

def _headers(last_modified):
    value=last_modified or clock.now()
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return {"Cache-Control":"public, max-age=60","Last-Modified":format_datetime(value.astimezone(timezone.utc),usegmt=True),"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET, OPTIONS","Access-Control-Allow-Headers":"*"}

def _works(db):
    cached=_cache.get("works")
    if cached and monotonic()-cached[0]<60:return cached[1]
    rows=db.execute(text("select w.id,w.ref_no,w.title,w.purpose,w.category::text category,w.status::text status,w.road_name,wd.name ward_name,a.name agency_name,w.planned_start,w.original_target_end,w.current_target_end,w.actual_start,w.actual_end,w.pct_complete,w.disruption_type::text disruption_type,w.disruption_note,w.last_update_at,w.updated_at,ST_AsGeoJSON(w.geometry)::json geometry from work w join agency a on a.id=w.agency_id left join ward wd on wd.id=w.ward_id where w.is_public order by w.ref_no")).mappings().all()
    result=([dict(r) for r in rows],max((r["updated_at"] or r["last_update_at"] for r in rows if r["updated_at"] or r["last_update_at"]),default=None))
    _cache["works"]=(monotonic(),result);return result

@router.get("/open/works.geojson")
def geojson(db=Depends(get_db)):
    rows,modified=_works(db)
    features=[]
    for row in rows:
        geometry=row["geometry"]
        props={key:value for key,value in row.items() if key not in ("id","geometry")}
        props["id"]=str(row["id"])
        props={k:(v.isoformat() if hasattr(v,"isoformat") else v) for k,v in props.items()}
        features.append({"type":"Feature","id":str(row["id"]),"geometry":geometry,"properties":props})
    return JSONResponse({"type":"FeatureCollection","features":features},headers=_headers(modified))

@router.get("/open/works.csv")
def csv_works(db=Depends(get_db)):
    rows,modified=_works(db); output=StringIO()
    fields=("ref_no","title","purpose","category","status","road_name","ward_name","agency_name","planned_start","original_target_end","current_target_end","actual_start","actual_end","pct_complete","disruption_type","disruption_note","last_update_at")
    writer=csv.DictWriter(output,fieldnames=fields,extrasaction="ignore");writer.writeheader()
    for row in rows:writer.writerow({k:v.isoformat() if hasattr(v,"isoformat") else v for k,v in row.items()})
    return Response(output.getvalue(),media_type="text/csv; charset=utf-8",headers={**_headers(modified),"Content-Disposition":"inline; filename=works.csv"})

@router.get("/open/stats.json")
def stats(db=Depends(get_db)):
    cached=_cache.get("stats")
    if cached and monotonic()-cached[0]<60:return JSONResponse(cached[1][0],headers=_headers(cached[1][1]))
    value=db.execute(text("select count(*) total,count(*) filter(where status::text='planned') planned,count(*) filter(where status::text in ('permitted','ongoing','paused')) active,count(*) filter(where status::text='ongoing') ongoing,count(*) filter(where current_target_end<:today and status::text not in ('completed','restoration_verified','closed')) delayed,count(*) filter(where status::text in ('completed','restoration_verified','closed')) completed from work where is_public"),{"today":clock.today()}).mappings().one()
    modified=db.execute(text("select max(updated_at) from work where is_public")).scalar()
    result={**dict(value),"as_of":clock.now().isoformat()};_cache["stats"]=(monotonic(),(result,modified))
    return JSONResponse(result,headers=_headers(modified))
