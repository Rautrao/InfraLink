from fastapi import APIRouter

router = APIRouter()

@router.get('/schedule_milestones/ping')
def ping():
    return {'module': 'schedule_milestones', 'status': 'scaffold'}

