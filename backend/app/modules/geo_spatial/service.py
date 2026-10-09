import json
from sqlalchemy import text

def locate_ward(geometry: dict, session=None, tenant_id=None):
    """Return a ward intersecting this GeoJSON geometry; owned geo interface stub."""
    if session is None:
        raise ValueError("locate_ward requires the caller transaction session")
    result = session.execute(text("""
        with g as (select ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326) as geom)
        select w.id
        from ward w cross join g
        where (cast(:tenant as uuid) is null or w.tenant_id=cast(:tenant as uuid))
          and w.boundary is not null and ST_Intersects(w.boundary,g.geom)
        order by ST_Contains(w.boundary,ST_PointOnSurface(g.geom)) desc,w.name
        limit 1
    """), {"geometry": json.dumps(geometry), "tenant": str(tenant_id) if tenant_id else None}).scalar()
    return result

def length_m(geometry: dict, session=None) -> float:
    """Measure GeoJSON geometry in metres using its geography representation."""
    if session is None:
        raise ValueError("length_m requires the caller transaction session")
    value = session.execute(text("""
        select case when ST_GeometryType(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326))='ST_Polygon'
                    then ST_Perimeter(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)::geography)
                    else ST_Length(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326)::geography) end
    """), {"geometry": json.dumps(geometry)}).scalar()
    return float(value or 0)
