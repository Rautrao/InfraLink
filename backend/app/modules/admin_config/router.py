import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from app.core.audit import write_audit
from app.core.db import get_db
from app.core.security import require_roles

router=APIRouter()

class CityConfigUpdate(BaseModel):
    buffer_m: float | None = Field(default=None, gt=0, le=1000)
    lookback_months: int | None = Field(default=None, ge=1, le=120)
    overdue_days: int | None = Field(default=None, ge=1, le=365)
    sla_day_ae: int | None = Field(default=None, ge=1, le=365)
    sla_day_ee: int | None = Field(default=None, ge=1, le=365)
    sla_day_se: int | None = Field(default=None, ge=1, le=365)
    sla_time_scale: float | None = Field(default=None, gt=0, le=1000)
    reason_codes: list[str] | None = None
    features: dict[str,bool] | None = None

    @model_validator(mode="after")
    def validate_rung_order(self):
        if self.sla_day_ae is not None and self.sla_day_ee is not None and self.sla_day_ee < self.sla_day_ae:
            raise ValueError("sla_day_ee must be greater than or equal to sla_day_ae")
        if self.sla_day_ee is not None and self.sla_day_se is not None and self.sla_day_se < self.sla_day_ee:
            raise ValueError("sla_day_se must be greater than or equal to sla_day_ee")
        if self.reason_codes is not None and (not self.reason_codes or len(set(self.reason_codes)) != len(self.reason_codes) or any(not x.strip() for x in self.reason_codes)):
            raise ValueError("reason_codes must be nonempty, unique strings")
        return self

def _serialize(row):
    return {"tenant_id":str(row["tenant_id"]),"buffer_m":float(row["buffer_m"]),"lookback_months":row["lookback_months"],"overdue_days":row["overdue_days"],"sla_day_ae":row["sla_day_ae"],"sla_day_ee":row["sla_day_ee"],"sla_day_se":row["sla_day_se"],"sla_time_scale":float(row["sla_time_scale"]),"reason_codes":row["reason_codes"],"features":row["features"]}

@router.get("/admin_config/ping")
def ping(): return {"module":"admin_config","status":"ready"}

@router.get("/admin/config")
def get_config(db=Depends(get_db),user=Depends(require_roles("admin"))):
    row=db.execute(text("select * from city_config where tenant_id=cast(:tenant as uuid)"),{"tenant":str(user["tenant_id"])}).mappings().first()
    if not row: raise HTTPException(404,"City configuration not found")
    return _serialize(row)

@router.put("/admin/config")
def put_config(body:CityConfigUpdate,db=Depends(get_db),user=Depends(require_roles("admin"))):
    before=db.execute(text("select * from city_config where tenant_id=cast(:tenant as uuid)"),{"tenant":str(user["tenant_id"])}).mappings().first()
    if not before: raise HTTPException(404,"City configuration not found")
    changes=body.model_dump(exclude_unset=True)
    if not changes: return _serialize(before)
    values={**_serialize(before),**changes}
    if values["sla_day_ee"] < values["sla_day_ae"] or values["sla_day_se"] < values["sla_day_ee"]:
        raise HTTPException(422,"SLA days must increase from AE to EE to SE")
    assignments=[]; params={"tenant":str(user["tenant_id"])}
    for key,value in changes.items():
        if key in ("reason_codes","features"):
            assignments.append(f"{key}=cast(:{key} as jsonb)"); params[key]=json.dumps(value)
        else:
            assignments.append(f"{key}=:{key}"); params[key]=value
    db.execute(text(f"update city_config set {','.join(assignments)} where tenant_id=cast(:tenant as uuid)"),params)
    after={**_serialize(before),**changes}
    write_audit(db,user,"config_updated","city_config",user["tenant_id"],before=_serialize(before),after=after)
    db.commit()
    result=db.execute(text("select * from city_config where tenant_id=cast(:tenant as uuid)"),{"tenant":str(user["tenant_id"])}).mappings().one()
    return _serialize(result)
