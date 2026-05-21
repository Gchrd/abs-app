from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .settings import settings
from .database import Base, engine
from .api import devices, jobs, backups
from .services import scheduler
from .routers import users as users_router, schedules as schedules_router, audit as audit_router, auth as auth_router
from sqlalchemy import text, inspect

Base.metadata.create_all(bind=engine)

def run_migrations():
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('backups')]
    if "batch_id" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE backups ADD COLUMN batch_id VARCHAR(128)"))

run_migrations()

app = FastAPI(title="ABS Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health(): return {"status":"ok"}

app.include_router(devices.router)
app.include_router(jobs.router)
app.include_router(backups.router)
app.include_router(users_router.router)
app.include_router(schedules_router.router)
app.include_router(audit_router.router)
app.include_router(auth_router.router)

def _recalculate_all_hashes():
    """
    Silently recalculate all backup hashes at startup using normalized sanitize_config.
    This fixes false-positive 'Changed' statuses caused by \r\n vs \n inconsistencies
    that may have been stored in previous backups. Runs transparently — no user action needed.
    """
    import logging
    from hashlib import sha256
    from pathlib import Path
    from .database import SessionLocal
    from .models import Backup, Device
    from .utils.config_sanitizer import sanitize_config

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    updated = 0
    try:
        backups = db.query(Backup).filter(Backup.status == "success").all()
        for b in backups:
            p = Path(b.path)
            if not p.exists():
                continue
            try:
                dev = db.get(Device, b.device_id)
                vendor = dev.vendor if dev else "cisco_ios"
                raw = p.read_bytes()
                content_str = raw.decode("utf-8", errors="ignore")
                clean = sanitize_config(content_str, vendor=vendor)
                new_hash = sha256(clean.encode("utf-8")).hexdigest()[:8]
                if b.hash != new_hash:
                    b.hash = new_hash
                    updated += 1
            except Exception:
                pass
        if updated:
            db.commit()
            logger.info(f"[startup] Recalculated {updated} backup hash(es) for consistency.")
    except Exception as e:
        logger.warning(f"[startup] Hash recalculation skipped: {e}")
    finally:
        db.close()


@app.on_event("startup")
async def on_startup():
    # Ensure default users exist after tables are created
    users_router._ensure_default_users()
    schedules_router._ensure_default_schedule()
    audit_router._ensure_example_audit()
    # Silently fix any hash inconsistencies from previous runs
    _recalculate_all_hashes()
    scheduler.start()
