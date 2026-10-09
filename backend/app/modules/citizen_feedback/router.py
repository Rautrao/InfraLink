from fastapi import APIRouter

router = APIRouter()

@router.get('/citizen_feedback/ping')
def ping():
    return {'module': 'citizen_feedback', 'status': 'scaffold'}

