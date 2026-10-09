from fastapi import APIRouter

router = APIRouter()

@router.get('/admin_config/ping')
def ping():
    return {'module': 'admin_config', 'status': 'scaffold'}

