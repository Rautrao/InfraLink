from fastapi import APIRouter

router = APIRouter()

@router.get('/project_registry/ping')
def ping():
    return {'module': 'project_registry', 'status': 'scaffold'}

