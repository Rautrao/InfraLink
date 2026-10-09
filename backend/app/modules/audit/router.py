from fastapi import APIRouter

router = APIRouter()

@router.get('/audit/ping')
def ping():
    return {'module': 'audit', 'status': 'scaffold'}

