from fastapi import APIRouter

router = APIRouter()

@router.get('/conflict_engine/ping')
def ping():
    return {'module': 'conflict_engine', 'status': 'scaffold'}

