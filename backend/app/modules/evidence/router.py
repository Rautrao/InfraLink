from fastapi import APIRouter

router = APIRouter()

@router.get('/evidence/ping')
def ping():
    return {'module': 'evidence', 'status': 'scaffold'}

