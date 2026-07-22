from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Device, Job, Backup
from ..utils.crypto import dec
from ..utils.timeutil import tznow
from ..services.netmiko_worker import fetch_running_config, NonRetryableBackupError
from ..services.job_controller import submit
from ..utils.config_sanitizer import sanitize_config
from hashlib import sha256
from pathlib import Path
from ..security import get_current_user, require_admin
from ..services.audit_log import audit_event
import asyncio

router = APIRouter(prefix="/jobs", tags=["jobs"])
def get_db():
    db = SessionLocal();
    try: yield db
    finally: db.close()


def _device_to_dict(d: Device) -> dict:
    """Extract a Device ORM row into a plain dict (with decrypted credentials)
    so it can safely cross into a background task after the request's db
    session/ORM objects are gone."""
    return {
        'id': d.id,
        'hostname': d.hostname,
        'ip': d.ip,
        'vendor': d.vendor,
        'protocol': d.protocol,
        'port': d.port,
        'username': dec(d.username_enc),
        'password': dec(d.password_enc),
        'secret': dec(d.secret_enc) if d.secret_enc else None,
    }


async def _run_backup_devices(job_id: int, device_list: list[dict], triggered_username: str, audit_action: str):
    """Background task - receives job_id and device dicts, NOT ORM objects.
    Shared by both the "backup all enabled devices" and "backup a single
    device" endpoints, so both get the same retry/logging/status behavior."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        log_lines = []
        ok = 0
        batch_id = f"manual_{job_id}_{tznow().strftime('%Y%m%d_%H%M%S')}"

        log_lines.append(f"Job started at {job.started_at.isoformat()}")
        log_lines.append(f"Processing {len(device_list)} device(s)...")

        max_attempts = 4
        retry_delays = [15, 30, 60]

        for idx, device_info in enumerate(device_list):
            for attempt in range(max_attempts):
                try:
                    if attempt == 0:
                        log_lines.append(f"[{device_info['hostname']}] Connecting to {device_info['ip']}...")
                    else:
                        log_lines.append(f"[{device_info['hostname']}] Retrying backup...")

                    # Fetch running config
                    path, content = fetch_running_config(
                        vendor=device_info['vendor'],
                        host=device_info['ip'],
                        username=device_info['username'],
                        password=device_info['password'],
                        secret=device_info['secret'],
                        protocol=device_info['protocol'],
                        port=device_info['port']
                    )

                    # Sanitize content for hashing (ignore timestamps)
                    content_str = content.decode('utf-8', errors='ignore')
                    clean_content_str = sanitize_config(content_str, vendor=device_info['vendor'])
                    clean_hash = sha256(clean_content_str.encode('utf-8')).hexdigest()[:8]

                    # Save backup record
                    b = Backup(
                        device_id=device_info['id'],
                        size_bytes=len(content),
                        hash=clean_hash,
                        path=str(path),
                        batch_id=batch_id
                    )
                    db.add(b)
                    ok += 1
                    db.commit()
                    log_lines.append(f"[{device_info['hostname']}] Backup success ({len(content)} bytes, path={path})")
                    break  # Success, exit retry loop

                except NonRetryableBackupError as e:
                    # Device rejected the command itself - retrying with the same
                    # command will fail the same way every time. Fail fast instead
                    # of wasting ~105s and risking tripping the device's own
                    # lockout policy from repeated attempts.
                    log_lines.append(f"[{device_info['hostname']}] Backup failed (not retrying - device rejected the command): ({str(e)})")
                    break

                except Exception as e:
                    if attempt < max_attempts - 1:
                        log_lines.append(f"[{device_info['hostname']}] Backup failed... ({str(e)})")
                        delay = retry_delays[attempt]
                        await asyncio.sleep(delay)
                    else:
                        log_lines.append(f"[{device_info['hostname']}] Backup failed: ({str(e)})")

            # Delay between devices (rate limiting)
            if idx < len(device_list) - 1:
                log_lines.append(f"[{device_info['hostname']}] Waiting 3s before next device...")
                await asyncio.sleep(3)

        # Update job status
        log_lines.append(f"Job completed: {ok}/{len(device_list)} successful")

        job.status = "success" if ok > 0 else "failed"
        job.devices = ok
        job.finished_at = tznow()
        job.log = "\n".join(log_lines)
        db.commit()

        audit_event(user=triggered_username, action=audit_action, target=f"job#{job_id}", result=f"{job.status} ({ok}/{len(device_list)} devices)")

    finally:
        db.close()


@router.post("/run/manual")
async def run_manual(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    # Create job record
    job = Job(triggered_by="manual", status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    # Get devices and extract to plain dicts
    devices = db.query(Device).filter_by(enabled=True).all()
    device_list = [_device_to_dict(d) for d in devices]

    audit_event(user=current_user.username, action="job_run_manual", target=f"job#{job.id}", result="started")

    # Submit task with job_id (not job object!) and device dicts
    await submit(lambda: _run_backup_devices(job.id, device_list, current_user.username, "job_run_manual"))

    return {"queued": True}


@router.post("/run/manual/{device_id}")
async def run_manual_device(device_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """Backup a single device on demand, regardless of its enabled/disabled state -
    useful for retesting one switch (e.g. after a config fix) without waiting
    for/triggering a full batch run across every device."""
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Device not found")

    job = Job(triggered_by=f"manual ({d.hostname})", status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    device_list = [_device_to_dict(d)]

    audit_event(user=current_user.username, action="job_run_manual_device", target=d.hostname, result="started")

    await submit(lambda: _run_backup_devices(job.id, device_list, current_user.username, "job_run_manual_device"))

    return {"queued": True, "job_id": job.id}


@router.get("")
def list_jobs(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # return recent jobs (most recent first)
    rows = db.query(Job).order_by(Job.started_at.desc()).limit(100).all()
    out = []
    for r in rows:
        out.append({
            "id": r.id,
            "triggered_by": r.triggered_by,
            "devices": r.devices or 0,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "log": r.log,
        })
    return out


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": j.id,
        "triggered_by": j.triggered_by,
        "status": j.status,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        "devices_count": j.devices or 0,
        "log": j.log or ""
    }


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    j = db.get(Job, job_id)
    if not j:
        return {"error": "not found"}
    if j.status != 'running':
        return {"ok": False, "detail": "job not running"}
    j.status = 'failed'
    from datetime import datetime
    j.finished_at = tznow()
    db.commit()
    audit_event(user=current_user.username, action="job_cancel", target=f"job#{job_id}", result="success")
    return {"ok": True}
