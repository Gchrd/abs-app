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

@app.on_event("startup")
async def on_startup():
    # Ensure default users exist after tables are created
    users_router._ensure_default_users()
    schedules_router._ensure_default_schedule()
    audit_router._ensure_example_audit()
    scheduler.start()
