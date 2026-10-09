from fastapi import APIRouter

router = APIRouter()

@router.get('/permits/ping')
def ping():
    return {'module': 'permits', 'status': 'scaffold'}

