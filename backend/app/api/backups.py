from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse, StreamingResponse
from ..database import SessionLocal
import io
import zipfile
from datetime import datetime
from sqlalchemy import func
from ..models import Backup, Device
from pathlib import Path
from ..security import get_current_user, require_admin
from ..services.audit_log import audit_event

router = APIRouter(prefix="/backups", tags=["backups"])
def get_db(): 
    db = SessionLocal(); 
    try: yield db
    finally: db.close()

@router.get("")
def list_backups(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Backup).order_by(Backup.timestamp.desc()).all()
    out = []
    for b in rows:
        dev = db.get(Device, b.device_id)
        out.append({
            "id": b.id,
            "device_id": b.device_id,
            "device_name": dev.hostname if dev else str(b.device_id),
            "timestamp": b.timestamp,
            "size": b.size_bytes,
            "hash": b.hash,
            "status": b.status,
            "path": b.path,
        })
    return out

@router.get("/active")
def list_active_backups(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return 1 active backup per device. status_changed = True if a NEWER backup exists with different hash."""
    db.expire_all()
    devices = db.query(Device).filter(Device.enabled == True).all()
    out = []
    for dev in devices:
        # Always get the latest successful backup first
        latest = (
            db.query(Backup)
            .filter(Backup.device_id == dev.id, Backup.status == "success")
            .order_by(Backup.timestamp.desc())
            .first()
        )
        if not latest:
            continue

        # Determine active backup
        if dev.active_backup_id is None:
            active = latest
        else:
            active = db.get(Backup, dev.active_backup_id)
            if not active:
                active = latest

        # Compare active vs the LATEST backup
        # If they're the same → Unchanged
        # If latest is NEWER than active AND hash differs → Changed
        if active.id == latest.id:
            status_changed = False
            newer_backup_id = None
        elif dev.last_ack_backup_id and dev.last_ack_backup_id == latest.id:
            # Admin already acknowledged this latest backup → treat as Unchanged
            status_changed = False
            newer_backup_id = None
        else:
            status_changed = (latest.hash != active.hash)
            newer_backup_id = latest.id if status_changed else None

        out.append({
            "device_id": dev.id,
            "device_name": dev.hostname,
            "backup_id": active.id,
            "timestamp": active.timestamp,
            "size": active.size_bytes,
            "hash": active.hash,
            "status_changed": status_changed,
            "previous_backup_id": newer_backup_id,  # ID of the newer backup (for diff)
        })
    return out


@router.put("/{backup_id}/set-active")
def set_active_backup(
    backup_id: int,
    body: dict = {},
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Set a backup as the active backup for its device. Optionally acknowledge a latest backup."""
    from fastapi import Body
    b = db.get(Backup, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")
    if b.status != "success":
        raise HTTPException(400, "Only successful backups can be set as active")

    dev = db.get(Device, b.device_id)
    if not dev:
        raise HTTPException(404, "Device not found")

    dev.active_backup_id = backup_id
    db.commit()

    audit_event(
        user=current_user.username,
        action="backup_set_active",
        target=f"{dev.hostname} (backup #{backup_id})",
        result="success"
    )
    return {"message": "Active backup updated", "device_id": dev.id, "backup_id": backup_id}

@router.put("/{backup_id}/acknowledge")
def acknowledge_backup(backup_id: int, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """Mark a backup as acknowledged (last seen by admin). Clears the 'Config Changed' alert."""
    b = db.get(Backup, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")

    dev = db.get(Device, b.device_id)
    if not dev:
        raise HTTPException(404, "Device not found")

    dev.last_ack_backup_id = backup_id
    db.commit()
    return {"message": "Backup acknowledged", "device_id": dev.id, "ack_backup_id": backup_id}

@router.get("/diff")
def get_diff(current: int, previous: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the raw text of two backup files for diff comparison in the frontend."""
    b_current = db.get(Backup, current)
    b_previous = db.get(Backup, previous)

    if not b_current:
        raise HTTPException(404, f"Backup #{current} not found")
    if not b_previous:
        raise HTTPException(404, f"Backup #{previous} not found")

    def read_file(path: str) -> str:
        p = Path(path)
        if not p.exists():
            return "(File not found on disk)"
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"(Error reading file: {e})"

    return {
        "current": read_file(b_current.path),
        "previous": read_file(b_previous.path),
        "current_backup_id": b_current.id,
        "previous_backup_id": b_previous.id,
    }

@router.get("/{backup_id}/download")
def download_backup(backup_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    b = db.get(Backup, backup_id)
    if not b or not Path(b.path).exists():
        raise HTTPException(404, "Not found")
    dev = db.get(Device, b.device_id)
    device_name = dev.hostname if dev else str(b.device_id)
    audit_event(user=current_user.username, action="backup_download", target=f"{device_name} ({b.timestamp.strftime('%Y-%m-%d %H:%M')})", result="success")
    return FileResponse(b.path, filename=Path(b.path).name, media_type="text/plain")

@router.delete("/{backup_id}")
def delete_backup(backup_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    b = db.get(Backup, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")
    
    dev = db.get(Device, b.device_id)
    device_name = dev.hostname if dev else str(b.device_id)
    
    # Delete file from filesystem
    try:
        file_path = Path(b.path)
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        audit_event(user=current_user.username, action="backup_delete", target=f"{device_name} ({b.timestamp.strftime('%Y-%m-%d %H:%M')})", result="failed")
        raise HTTPException(500, f"Failed to delete file: {str(e)}")
    
    # Delete from database
    db.delete(b)
    db.commit()
    
    audit_event(user=current_user.username, action="backup_delete", target=f"{device_name} ({b.timestamp.strftime('%Y-%m-%d %H:%M')})", result="success")
    return {"message": "Backup deleted successfully"}


@router.get("/download-date/{date_str}")
def download_backup_date(date_str: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Download a ZIP file containing all backups for the specified date (YYYY-MM-DD).
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format, expected YYYY-MM-DD")

    # Get backups where timestamp cast to date matches the target date
    # Compatible with SQLite via func.date
    backups = db.query(Backup).filter(func.date(Backup.timestamp) == target_date.isoformat()).all()
    
    if not backups:
        raise HTTPException(404, f"No backups found for date {date_str}")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for b in backups:
            dev = db.get(Device, b.device_id)
            if not dev:
                continue
            
            p = Path(b.path)
            if p.exists():
                # filename formatting: hostname_timestamp.txt
                timestamp_str = b.timestamp.strftime('%H%M%S')
                filename = f"{dev.hostname}_{timestamp_str}_{p.name}"
                zip_file.write(p, arcname=filename)
                
    zip_buffer.seek(0)
    
    audit_event(user=current_user.username, action="backup_download_batch", target=f"date: {date_str}", result=f"success ({len(backups)} files)")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=backups_{date_str}.zip"}
    )

@router.delete("/date/{date_str}")
def delete_backup_date(date_str: str, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """
    Deletes all backups for a specific date (YYYY-MM-DD), but ONLY if none of them are marked as active/locked.
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Invalid date format, expected YYYY-MM-DD")

    backups = db.query(Backup).filter(func.date(Backup.timestamp) == target_date.isoformat()).all()
    
    if not backups:
        raise HTTPException(404, f"No backups found for date {date_str}")

    # Validation: Check if ANY backup in this date is active or acknowledged
    # This prevents deleting backups that are currently set as the "reference"
    for b in backups:
        dev = db.get(Device, b.device_id)
        if dev:
            if dev.active_backup_id == b.id or dev.last_ack_backup_id == b.id:
                raise HTTPException(403, f"Cannot delete date {date_str} because backup ID {b.id} is currently locked/active for device {dev.hostname}.")

    deleted_count = 0
    for b in backups:
        try:
            file_path = Path(b.path)
            if file_path.exists():
                file_path.unlink() # Delete the physical text file
        except Exception as e:
            # Continue deleting others even if one text file fails
            print(f"Warning: Failed to delete physical file {b.path}: {e}")
        
        db.delete(b)
        deleted_count += 1

    db.commit()
    
    audit_event(user=current_user.username, action="backup_delete_batch", target=f"date: {date_str}", result=f"success (deleted {deleted_count} backups)")
    return {"message": f"Successfully deleted {deleted_count} backups for date {date_str}"}
