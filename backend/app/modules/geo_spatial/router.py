from fastapi import APIRouter

router = APIRouter()

@router.get('/geo_spatial/ping')
def ping():
    return {'module': 'geo_spatial', 'status': 'scaffold'}

