from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Device, Job, Backup
from ..utils.crypto import dec
from ..utils.timeutil import tznow
from ..services.netmiko_worker import fetch_running_config
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

@router.post("/run/manual")
async def run_manual(db: Session = Depends(get_db), current_user=Depends(require_admin)):
    async def task(job_id: int, device_list: list[dict]):
        """Background task - receives job_id and device dicts, NOT ORM objects"""
        db = SessionLocal()
        try:
            # Re-query job with fresh session
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            
            log_lines = []
            ok = 0
            
            log_lines.append(f"Job started at {job.started_at.isoformat()}")
            log_lines.append(f"Processing {len(device_list)} enabled device(s)...")
            
            max_attempts = 4
            retry_delays = [15, 30, 60]

            for idx, device_info in enumerate(device_list):
                for attempt in range(max_attempts):
                    try:
                        if attempt == 0:
                            log_lines.append(f"[{device_info['hostname']}] Connecting to {device_info['ip']}...")
                        else:
                            log_lines.append(f"[{device_info['hostname']}] Mencoba backup ulang...")

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
                        # fetch_running_config returns bytes, so decode first
                        content_str = content.decode('utf-8', errors='ignore')
                        clean_content_str = sanitize_config(content_str, vendor=device_info['vendor'])
                        clean_hash = sha256(clean_content_str.encode('utf-8')).hexdigest()[:8]

                        # Save backup record
                        b = Backup(
                            device_id=device_info['id'], 
                            size_bytes=len(content),
                            hash=clean_hash, 
                            path=str(path)
                        )
                        db.add(b)
                        ok += 1
                        db.commit()
                        log_lines.append(f"[{device_info['hostname']}] Backup success ({len(content)} bytes, path={path})")
                        break  # Success, exit retry loop

                    except Exception as e:
                        if attempt < max_attempts - 1:
                            log_lines.append(f"[{device_info['hostname']}] Backup gagal... ({str(e)})")
                            delay = retry_delays[attempt]
                            await asyncio.sleep(delay)
                        else:
                            log_lines.append(f"[{device_info['hostname']}] Backup failed: ({str(e)})")

                # Delay between devices (rate limiting)
                if idx < len(device_list) - 1:
                    log_lines.append(f"[{device_info['hostname']}] Waiting 3s before next device...")
                    await asyncio.sleep(3)
            
            # Update job status
            from datetime import datetime
            log_lines.append(f"Job completed: {ok}/{len(device_list)} successful")
            
            job.status = "success"
            job.devices = ok
            job.finished_at = tznow()
            job.log = "\n".join(log_lines)
            db.commit()
            
            audit_event(user=current_user.username, action="job_run_manual", target=f"job#{job_id}", result=f"success ({ok}/{len(device_list)} devices)")
            
        finally:
            db.close()
    
    # Create job record
    job = Job(triggered_by="manual", status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Get devices and extract to plain dicts
    devices = db.query(Device).filter_by(enabled=True).all()
    device_list = []
    for d in devices:
        device_list.append({
            'id': d.id,
            'hostname': d.hostname,
            'ip': d.ip,
            'vendor': d.vendor,
            'protocol': d.protocol,
            'port': d.port,
            'username': dec(d.username_enc),
            'password': dec(d.password_enc),
            'secret': dec(d.secret_enc) if d.secret_enc else None,
        })
    
    audit_event(user=current_user.username, action="job_run_manual", target=f"job#{job.id}", result="started")
    
    # Submit task with job_id (not job object!) and device dicts
    await submit(lambda: task(job.id, device_list))
    
    return {"queued": True}


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
