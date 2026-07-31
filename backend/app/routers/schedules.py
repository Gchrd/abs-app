from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Schedule
from ..schemas import ScheduleIn, ScheduleOut
import time
from ..security import get_current_user, require_admin
from ..services.audit_log import audit_event
from ..services import scheduler as sched_service

router = APIRouter(prefix="/schedules", tags=["schedules"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_default_schedule():
    # No default schedule - users should create their own
    pass


def _next_run_for(schedule_id: int):
    """Look up the next fire time APScheduler actually has queued for this
    schedule, rather than recomputing it ourselves - it already tracks this
    per-job (accounting for the configured interval, run time, and timezone)
    and is the one source of truth for when a schedule will really run next."""
    job = sched_service.scheduler.get_job(f"schedule-{schedule_id}")
    # next_run_time is only populated once the scheduler has actually been
    # started (e.g. never in the test suite, which disables the startup
    # hook) - the attribute doesn't exist at all before that, rather than
    # just being None, so access it defensively.
    return getattr(job, "next_run_time", None) if job else None


@router.get("", response_model=list[ScheduleOut])
def list_schedules(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Schedule).all()
    out = []
    for r in rows:
        out.append(ScheduleOut(
            id=r.id, name=r.name, run_at=r.run_at, enabled=bool(r.enabled),
            interval_days=r.interval_days, target_type=r.target_type,
            target_tags=r.target_tags, retention=r.retention, notify_on_fail=bool(r.notify_on_fail),
            next_run=_next_run_for(r.id)
        ))
    return out


@router.post("", response_model=ScheduleOut)
def create_schedule(payload: ScheduleIn, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    # Use provided name or generate one
    name = payload.name or (f"device-{payload.device_id}-{int(time.time())}" if payload.device_id else f"schedule-{int(time.time())}")
    interval = payload.interval_days or 7
    
    # Determine target type
    if payload.target_type:
        target_type = payload.target_type
    elif payload.device_id:
        target_type = "Device"
    else:
        target_type = "All"
    
    s = Schedule(
        name=name, 
        run_at=payload.schedule_time, 
        enabled=payload.enabled,
        interval_days=interval, 
        target_type=target_type,
        target_tags=payload.target_tags
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    audit_event(user=current_user.username, action="schedule_create", target=s.name, result="success")
    # Reload scheduler to pick up new schedule
    sched_service.reload_schedules()
    return ScheduleOut(
        id=s.id, name=s.name, run_at=s.run_at, enabled=bool(s.enabled),
        interval_days=s.interval_days, target_type=s.target_type,
        target_tags=s.target_tags, retention=s.retention, notify_on_fail=bool(s.notify_on_fail),
        next_run=_next_run_for(s.id)
    )


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: int, payload: ScheduleIn, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    s = db.get(Schedule, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="not found")
    s.run_at = payload.schedule_time
    s.enabled = payload.enabled
    if payload.interval_days:
        s.interval_days = payload.interval_days
    if payload.name:
        s.name = payload.name
    if payload.target_type:
        s.target_type = payload.target_type
    if payload.target_tags is not None:  # Allow empty string to clear tags
        s.target_tags = payload.target_tags
    if payload.device_id:
        s.name = f"device-{payload.device_id}"
        s.target_type = "Device"
    db.commit()
    db.refresh(s)
    audit_event(user=current_user.username, action="schedule_update", target=s.name, result="success")
    # Reload scheduler to pick up changes
    sched_service.reload_schedules()
    return ScheduleOut(
        id=s.id, name=s.name, run_at=s.run_at, enabled=bool(s.enabled),
        interval_days=s.interval_days, target_type=s.target_type,
        target_tags=s.target_tags, retention=s.retention, notify_on_fail=bool(s.notify_on_fail),
        next_run=_next_run_for(s.id)
    )


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    s = db.get(Schedule, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="not found")
    schedule_name = s.name
    db.delete(s)
    db.commit()
    audit_event(user=current_user.username, action="schedule_delete", target=schedule_name, result="success")
    # Reload scheduler to remove deleted schedule
    sched_service.reload_schedules()
    return {"deleted": True}
