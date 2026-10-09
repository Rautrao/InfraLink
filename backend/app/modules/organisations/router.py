from fastapi import APIRouter

router = APIRouter()

@router.get('/organisations/ping')
def ping():
    return {'module': 'organisations', 'status': 'scaffold'}

