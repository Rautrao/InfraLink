from fastapi import APIRouter

router = APIRouter()

@router.get('/notifications/ping')
def ping():
    return {'module': 'notifications', 'status': 'scaffold'}

