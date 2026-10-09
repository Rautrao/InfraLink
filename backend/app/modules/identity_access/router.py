from datetime import date
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.core.db import get_db
from app.core.security import create_token, get_current_user, verify_password

router = APIRouter()
_otp = {}

class LoginBody(BaseModel):
    email: str
    password: str
class PhoneBody(BaseModel): phone: str
class OtpBody(BaseModel): phone: str; otp: str

def public_user(row):
    return {"id": str(row["id"]), "tenant_id": str(row["tenant_id"]), "name": row["name"], "email": row["email"], "phone": row["phone"], "role": row["role"], "agency_id": str(row["agency_id"]) if row["agency_id"] else None, "ward_id": str(row["ward_id"]) if row["ward_id"] else None, "zone_id": str(row["zone_id"]) if row["zone_id"] else None}

@router.post("/auth/login")
def login(body: LoginBody, db=Depends(get_db)):
    row = db.execute(text("select * from app_user where lower(email)=lower(:email) and active"), {"email": body.email}).mappings().first()
    if not row or not verify_password(body.password, row["password_hash"] or ""):
        raise HTTPException(401, detail={"code":"INVALID_CREDENTIALS","message":"Email or password is incorrect","details":None})
    user = public_user(row)
    return {"access_token": create_token(user), "token_type":"bearer", "user":user}

@router.post("/auth/otp/request")
def request_otp(body: PhoneBody, db=Depends(get_db)):
    exists = db.execute(text("select 1 from app_user where phone=:phone and role='resident' and active"), {"phone":body.phone}).scalar()
    if not exists: raise HTTPException(404, "Resident mobile number not found")
    code = "123456"
    _otp[body.phone] = code
    print(f"[DEV OTP] {body.phone}: {code}", flush=True)
    return {"message":"OTP sent"}

@router.post("/auth/otp/verify")
def verify_otp(body: OtpBody, db=Depends(get_db)):
    if body.otp != "123456" or _otp.get(body.phone) != body.otp:
        raise HTTPException(401, "Invalid or expired OTP")
    row = db.execute(text("select * from app_user where phone=:phone and role='resident' and active"), {"phone":body.phone}).mappings().first()
    if not row: raise HTTPException(404, "Resident not found")
    user = public_user(row); _otp.pop(body.phone, None)
    return {"access_token": create_token(user), "token_type":"bearer", "user":user}

@router.get("/auth/me")
def me(user=Depends(get_current_user)): return user

@router.get("/config/public")
def public_config(db=Depends(get_db)):
    row = db.execute(text("select reason_codes from city_config order by tenant_id limit 1")).scalar()
    return {"reason_codes":row or [],"categories":["road_cut","resurfacing","water_pipeline","sewer","drainage","electricity","telecom_duct","gas_pipeline","metro","footpath","other"],"statuses":["planned","permitted","ongoing","paused","completed","restoration_verified","closed"],"city_center":{"lat":18.5204,"lng":73.8567}}
