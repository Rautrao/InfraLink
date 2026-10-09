from fastapi import APIRouter

router = APIRouter()

@router.get('/imports/ping')
def ping():
    return {'module': 'imports', 'status': 'scaffold'}

