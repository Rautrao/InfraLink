from fastapi import APIRouter

router = APIRouter()

@router.get('/public_api/ping')
def ping():
    return {'module': 'public_api', 'status': 'scaffold'}

