from fastapi import HTTPException
from fastapi.responses import JSONResponse

class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        super().__init__(status_code, detail={"code": code, "message": message, "details": details})

async def error_handler(request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error = detail
    else:
        error = {"code": "HTTP_ERROR", "message": str(detail), "details": None}
    return JSONResponse(status_code=exc.status_code, content={"error": error})
