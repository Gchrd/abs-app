from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, time
from ..utils.timeutil import tznow
from ..settings import settings
from ..database import SessionLocal
from ..models import Schedule, Device, Job, Backup
from ..utils.crypto import dec
from .netmiko_worker import fetch_running_config
from ..utils.config_sanitizer import sanitize_config
from .audit_log import audit_event
from hashlib import sha256
import pytz
import asyncio

scheduler = AsyncIOScheduler(timezone=pytz.timezone(settings.TIMEZONE))


async def run_scheduled_backup(schedule_id: int, schedule_name: str):
    """
    Execute a scheduled backup job for a specific schedule.
    This function runs the actual backup logic.
    """
    db = SessionLocal()
    try:
        # Create job record
        job = Job(
            triggered_by=f"schedule:{schedule_name}",
            status="running"
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        job_id = job.id  # Extract job_id before session operations
        
        log_lines = []
        log_lines.append(f"Scheduled job started at {job.started_at.isoformat()}")
        log_lines.append(f"Schedule: {schedule_name}")
        
        # Get schedule configuration to filter devices
        schedule = db.query(Schedule).filter_by(id=schedule_id).first()
        if not schedule:
            log_lines.append(f"ERROR: Schedule {schedule_id} not found")
            job.status = "failed"
            job.log = "\n".join(log_lines)
            db.commit()
            return
        
        # Filter devices based on target_type and target_tags
        query = db.query(Device).filter_by(enabled=True)
        
        if schedule.target_type == "Tag" and schedule.target_tags:
            # Filter by tags - device must have at least one matching tag
            target_tags = [t.strip() for t in schedule.target_tags.split(",") if t.strip()]
            log_lines.append(f"Target: Devices with tags [{', '.join(target_tags)}]")
            
            # Get devices that have ANY of the target tags
            filtered_devices = []
            for d in query.all():
                if d.tags:
                    device_tags = [t.strip().lower() for t in d.tags.split(",") if t.strip()]
                    if any(tag.lower() in device_tags for tag in target_tags):
                        filtered_devices.append(d)
            devices = filtered_devices
        else:
            # All enabled devices
            log_lines.append(f"Target: All enabled devices")
            devices = query.all()
        
        log_lines.append(f"Processing {len(devices)} device(s)...")
        
        # Extract device info with decrypted credentials
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
        
        ok = 0
        for idx, device_info in enumerate(device_list):
            try:
                log_lines.append(f"[{device_info['hostname']}] Connecting to {device_info['ip']}...")
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
                
                # Delay between devices (rate limiting)
                if idx < len(device_list) - 1:
                    log_lines.append(f"[{device_info['hostname']}] Waiting 3s before next device...")
                    await asyncio.sleep(3)
                
            except Exception as e:
                log_lines.append(f"[{device_info['hostname']}] Backup failed: {str(e)}")
                if idx < len(device_list) - 1:
                    await asyncio.sleep(2)
        
        # Update job status - re-query to avoid detached instance
        log_lines.append(f"Job completed: {ok}/{len(device_list)} successful")
        
        job = db.query(Job).filter_by(id=job_id).first()
        if job:
            job.status = "success"
            job.devices = ok
            job.finished_at = tznow()
            job.log = "\n".join(log_lines)
            db.commit()
        
        # Audit log
        audit_event(
            user="system",
            action="job_run_scheduled",
            target=f"schedule:{schedule_name}",
            result=f"success ({ok}/{len(device_list)} devices)"
        )
        
    except Exception as e:
        # Handle unexpected errors
        if 'job' in locals():
            job.status = "failed"
            job.finished_at = tznow()
            job.log = f"Job failed: {str(e)}"
            db.commit()
        audit_event(
            user="system",
            action="job_run_scheduled",
            target=f"schedule:{schedule_name}",
            result=f"failed: {str(e)}"
        )
    finally:
        db.close()


def load_schedules_from_db():
    """
    Load all enabled schedules from the database and register them with APScheduler.
    """
    db = SessionLocal()
    try:
        schedules = db.query(Schedule).filter_by(enabled=True).all()
        
        for sch in schedules:
            try:
                # Parse run_at time (format: "HH:MM")
                hour, minute = map(int, sch.run_at.split(":"))
                
                # Create interval trigger based on interval_days
                trigger = IntervalTrigger(
                    days=sch.interval_days,
                    start_date=datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0),
                    timezone=pytz.timezone(settings.TIMEZONE)
                )
                
                # Add job to scheduler
                scheduler.add_job(
                    run_scheduled_backup,
                    trigger=trigger,
                    args=(sch.id, sch.name),
                    id=f"schedule-{sch.id}",
                    replace_existing=True,
                    name=f"Scheduled Backup: {sch.name}"
                )
                print(f"[Scheduler] Loaded: {sch.name} (every {sch.interval_days} days at {sch.run_at})")
            except Exception as e:
                print(f"[Scheduler] Failed to load {sch.name}: {e}")
    finally:
        db.close()


def reload_schedules():
    """
    Reload all schedules from database. Call this after schedule changes.
    """
    # Remove all existing schedule jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("schedule-"):
            job.remove()
    
    # Load fresh schedules from DB
    load_schedules_from_db()


def start():
    """
    Start the scheduler and load initial schedules.
    """
    if not scheduler.running:
        scheduler.start()
        print("[Scheduler] APScheduler started")
        load_schedules_from_db()
