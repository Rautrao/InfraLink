import json
from sqlalchemy import text
from app.core.db import SessionLocal

def locate_ward(geometry: dict, session=None, tenant_id=None):
    """Return a ward intersecting this GeoJSON geometry; owned geo interface stub."""
    owns_session=session is None
    db=session or SessionLocal()
    try:
        return db.execute(text("""
            with g as (select ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) as geom)
            select w.id
            from ward w cross join g
            where (cast(:tenant as uuid) is null or w.tenant_id=cast(:tenant as uuid))
              and w.boundary is not null and ST_Intersects(w.boundary,g.geom)
            order by ST_Contains(w.boundary,ST_PointOnSurface(g.geom)) desc,w.name
            limit 1
        """), {"geometry": json.dumps(geometry), "tenant": str(tenant_id) if tenant_id else None}).scalar()
    finally:
        if owns_session: db.close()

def length_m(geometry: dict, session=None) -> float:
    """Measure GeoJSON geometry in metres using its geography representation."""
    owns_session=session is None
    db=session or SessionLocal()
    try:
        value = db.execute(text("""
            select case when ST_GeometryType(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326))='ST_Polygon'
                        then ST_Perimeter(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)::geography)
                        else ST_Length(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)::geography) end
        """), {"geometry": json.dumps(geometry)}).scalar()
        return float(value or 0)
    finally:
        if owns_session: db.close()

def validate_city_geometry(geometry: dict, tenant_id, session=None) -> bool:
    """Accept only valid LineStrings/Polygons fully covered by this city's wards."""
    owns_session=session is None
    db=session or SessionLocal()
    try:
        return bool(db.execute(text("""
            with g as (select ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) as geom),
                 city as (select ST_UnaryUnion(ST_Collect(boundary)) as geom from ward where tenant_id=cast(:tenant as uuid) and boundary is not null)
            select ST_IsValid(g.geom)
               and ST_GeometryType(g.geom) in ('ST_LineString','ST_Polygon')
               and city.geom is not null and ST_CoveredBy(g.geom,city.geom)
            from g cross join city
        """),{"geometry":json.dumps(geometry),"tenant":str(tenant_id)}).scalar())
    finally:
        if owns_session: db.close()
