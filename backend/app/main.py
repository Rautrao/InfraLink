from pathlib import Path
from contextlib import asynccontextmanager
from importlib import import_module
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.encoders import jsonable_encoder
from apscheduler.schedulers.background import BackgroundScheduler
from pydantic import BaseModel, Field
from sqlalchemy import text
from app.core.config import settings
from app.core.db import engine, SessionLocal
from app.core.errors import error_handler
from app.core.clock import advance, reset
from app.core.security import bearer, decode_token
from app.modules.identity_access.router import router as identity_router

MODULES = ["organisations","project_registry","schedule_milestones","audit","admin_config","imports","geo_spatial","permits","conflict_engine","evidence","citizen_feedback","notifications","reporting","public_api"]
scheduler = BackgroundScheduler(timezone="UTC")

class AdvanceTimeBody(BaseModel):
    days: int = Field(ge=-3650, le=3650)

def apply_schema():
    with engine.begin() as conn:
        tables = ["tenant", "zone", "ward", "agency", "app_user", "escalation_level", "work", "work_milestone", "work_date_revision", "work_status_history", "work_update", "evidence", "permit", "conflict_alert", "conflict_decision", "feedback_ticket", "ticket_event", "follow_subscription", "notification", "outbox_event", "audit_log", "city_config"]
        checks = " and ".join(f"to_regclass('public.{table}') is not null" for table in tables)
        complete = conn.execute(text(f"select {checks}")).scalar()
        if not complete:
            schema = Path(__file__).resolve().parents[1] / "sql" / "001_schema.sql"
            conn.exec_driver_sql(schema.read_text(encoding="utf-8"))
        else:
            conn.exec_driver_sql("ALTER TABLE feedback_ticket ADD COLUMN IF NOT EXISTS overdue_public boolean NOT NULL DEFAULT false")
            conn.exec_driver_sql("ALTER TABLE notification ADD COLUMN IF NOT EXISTS read_at timestamptz")

def dispatch_events():
    from app.core.events import dispatch_batch
    with SessionLocal() as session:
        try: dispatch_batch(session)
        except Exception: session.rollback()

def scan_overdue_updates():
    from app.core.jobs import check_overdue_updates
    check_overdue_updates()

def scan_feedback_sla():
    from app.modules.citizen_feedback.router import escalate_feedback
    escalate_feedback()

def notify_starting_tomorrow():
    from app.modules.notifications.router import notify_starting_tomorrow as send_starting
    send_starting()

def scan_conflicts_nightly():
    from app.modules.conflict_engine.router import scan_all_conflicts
    scan_all_conflicts()

@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_schema()
    if not scheduler.running:
        scheduler.add_job(dispatch_events,"interval",seconds=2,id="outbox",replace_existing=True)
        scheduler.add_job(scan_overdue_updates,"interval",minutes=5,id="overdue_updates",replace_existing=True)
        scheduler.add_job(scan_feedback_sla,"interval",minutes=1,id="feedback_sla",replace_existing=True)
        scheduler.add_job(notify_starting_tomorrow,"interval",hours=1,id="starting_tomorrow",replace_existing=True)
        scheduler.add_job(scan_conflicts_nightly,"interval",hours=24,id="conflict_scan",replace_existing=True)
        scheduler.start()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield
    if scheduler.running: scheduler.shutdown(wait=False)

app = FastAPI(title="Public Works Transparency Platform", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(HTTPException, error_handler)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={"error":{"code":"VALIDATION_ERROR","message":"Request validation failed","details":jsonable_encoder(exc.errors())}})
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(identity_router, prefix="/api/v1", tags=["identity and reference"])
for module in MODULES:
    module_router = import_module(f"app.modules.{module}.router").router
    app.include_router(module_router, prefix="/api/v1", tags=[module])
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=settings.upload_dir), name="files")

@app.get("/healthz")
def healthz(): return {"status":"ok"}

@app.post("/api/v1/dev/advance-time")
def advance_time(body: AdvanceTimeBody, credentials=Depends(bearer)):
    if not settings.dev_mode:
        if not credentials: raise HTTPException(401, "Authentication required")
        claims = decode_token(credentials.credentials)
        with SessionLocal() as db:
            role = db.execute(text("select role from app_user where id=:id and active"), {"id":claims["sub"]}).scalar()
        if role != "admin": raise HTTPException(403, "Admin role required")
    advance(body.days)
    from app.core.clock import now
    from app.modules.citizen_feedback.router import escalate_feedback
    escalated=escalate_feedback()
    return {"now": now().isoformat(), "advanced_days": body.days, "feedback_escalated": escalated}

@app.post("/api/v1/dev/reset-seed")
def reset_seed(credentials=Depends(bearer)):
    if not settings.dev_mode:
        if not credentials: raise HTTPException(401, "Authentication required")
        claims = decode_token(credentials.credentials)
        with SessionLocal() as db:
            role = db.execute(text("select role from app_user where id=:id and active"), {"id":claims["sub"]}).scalar()
        if role != "admin": raise HTTPException(403, "Admin role required")
    from seed.seed import main as seed_demo_city
    reset()
    seed_demo_city(reset=True)
    return {"status":"seed reset"}
