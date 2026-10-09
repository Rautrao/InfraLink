from fastapi import APIRouter

router = APIRouter()

@router.get('/reporting/ping')
def ping():
    return {'module': 'reporting', 'status': 'scaffold'}

