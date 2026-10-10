from datetime import timedelta
from functools import wraps
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from app.core.config import settings
from app.core.clock import now
from app.core.db import get_db

bearer = HTTPBearer(auto_error=False)
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, encoded: str) -> bool:
    try: return bcrypt.checkpw(password.encode(), encoded.encode())
    except (ValueError, TypeError): return False

def create_token(user: dict, expires_minutes: int = 720) -> str:
    return jwt.encode({"sub": str(user["id"]), "tenant_id": str(user["tenant_id"]), "role": user["role"], "exp": now() + timedelta(minutes=expires_minutes)}, settings.jwt_secret, algorithm="HS256")

def decode_token(token: str) -> dict:
    try: return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc: raise HTTPException(401, "Invalid or expired token") from exc

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    if not credentials: raise HTTPException(401, "Authentication required")
    claims = decode_token(credentials.credentials)
    user = db.execute(text("select id, tenant_id, agency_id, name, email, phone, role, ward_id, zone_id, active from app_user where id=:id and active"), {"id": claims["sub"]}).mappings().first()
    if not user: raise HTTPException(401, "User not found or inactive")
    return dict(user)

def get_optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    if not credentials:
        return None
    try:
        claims = decode_token(credentials.credentials)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise
    user = db.execute(text("select id, tenant_id, agency_id, name, email, phone, role, ward_id, zone_id, active from app_user where id=:id and active"), {"id": claims["sub"]}).mappings().first()
    if not user: raise HTTPException(401, "User not found or inactive")
    return dict(user)

def require_roles(*roles):
    def dependency(user=Depends(get_current_user)):
        if user["role"] not in roles: raise HTTPException(403, "Insufficient role")
        return user
    return dependency

def check_jurisdiction(user: dict, ward_id=None, agency_id=None):
    role = user["role"]
    if role == "junior_engineer" and ward_id and str(user.get("ward_id")) != str(ward_id): raise HTTPException(403, "Outside ward jurisdiction")
    if role == "utility_editor" and agency_id and str(user.get("agency_id")) != str(agency_id): raise HTTPException(403, "Outside agency jurisdiction")
    return True
