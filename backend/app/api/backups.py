from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse, StreamingResponse
from ..database import SessionLocal
import io
import zipfile
from datetime import datetime
from hashlib import sha256
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
            "batch_id": b.batch_id,
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
            if latest.hash == active.hash:
                status_changed = False
            else:
                # Fallback: Check if the actual sanitized contents are identical
                # This handles cases where old hashes in DB don't match new sanitizer logic
                try:
                    from ..utils.config_sanitizer import sanitize_config
                    p_active = Path(active.path)
                    p_latest = Path(latest.path)
                    if p_active.exists() and p_latest.exists():
                        raw_active = p_active.read_text(encoding="utf-8", errors="replace")
                        raw_latest = p_latest.read_text(encoding="utf-8", errors="replace")
                        vendor = dev.vendor if dev else "cisco_ios"
                        clean_active = sanitize_config(raw_active, vendor=vendor)
                        clean_latest = sanitize_config(raw_latest, vendor=vendor)
                        status_changed = (clean_active != clean_latest)
                    else:
                        status_changed = True
                except Exception:
                    status_changed = True

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


@router.get("/download-active")
def download_active_backups(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Download a ZIP file containing the currently ACTIVE backups for all devices.
    """
    db.expire_all()
    devices = db.query(Device).filter(Device.enabled == True).all()
    backups_to_zip = []

    for dev in devices:
        # Get the latest successful backup first
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
        
        backups_to_zip.append((dev, active))

    if not backups_to_zip:
        raise HTTPException(404, "No active backups found to download.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for dev, b in backups_to_zip:
            p = Path(b.path)
            if p.exists():
                # filename formatting: hostname_active_timestamp.txt
                timestamp_str = b.timestamp.strftime('%H%M%S')
                # Include the date as well so it's clearer
                date_str = b.timestamp.strftime('%Y%m%d')
                filename = f"{dev.hostname}_active_{date_str}_{timestamp_str}.txt"
                zip_file.write(p, arcname=filename)

    zip_buffer.seek(0)
    
    audit_event(user=current_user.username, action="backup_download_active_batch", target="active_backups", result=f"success ({len(backups_to_zip)} files)")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=active_backups_{timestamp}.zip"}
    )

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
    """Return sanitized text of two backup files for diff comparison in the frontend."""
    from ..utils.config_sanitizer import sanitize_config

    b_current = db.get(Backup, current)
    b_previous = db.get(Backup, previous)

    if not b_current:
        raise HTTPException(404, f"Backup #{current} not found")
    if not b_previous:
        raise HTTPException(404, f"Backup #{previous} not found")

    def read_file(path: str, vendor: str) -> str:
        p = Path(path)
        if not p.exists():
            return "(File not found on disk)"
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            return sanitize_config(raw, vendor=vendor)
        except Exception as e:
            return f"(Error reading file: {e})"

    # Get vendor from device for sanitization
    dev_current = db.get(Device, b_current.device_id)
    dev_previous = db.get(Device, b_previous.device_id)
    vendor_current = dev_current.vendor if dev_current else "cisco_ios"
    vendor_previous = dev_previous.vendor if dev_previous else "cisco_ios"

    return {
        "current": read_file(b_current.path, vendor_current),
        "previous": read_file(b_previous.path, vendor_previous),
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


@router.get("/download-batch/{batch_id}")
def download_backup_batch(batch_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Download a ZIP file containing all backups for the specified batch_id (or legacy date YYYY-MM-DD).
    """
    # Support legacy_ prefix sent by frontend for old backups
    lookup_id = batch_id
    if batch_id.startswith("legacy_"):
        lookup_id = batch_id[len("legacy_"):]

    try:
        target_date = datetime.strptime(lookup_id, "%Y-%m-%d").date()
        is_legacy = True
    except ValueError:
        is_legacy = False

    if is_legacy:
        backups = db.query(Backup).filter(func.date(Backup.timestamp) == target_date.isoformat()).all()
    else:
        backups = db.query(Backup).filter(Backup.batch_id == batch_id).all()
    
    if not backups:
        raise HTTPException(404, f"No backups found for batch {batch_id}")

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
    
    audit_event(user=current_user.username, action="backup_download_batch", target=f"batch: {batch_id}", result=f"success ({len(backups)} files)")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=backups_{batch_id}.zip"}
    )

@router.delete("/batch/{batch_id}")
def delete_backup_batch(batch_id: str, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    """
    Deletes all backups for a specific batch_id (or legacy date YYYY-MM-DD), but ONLY if none of them are marked as active/locked.
    """
    # Support legacy_ prefix sent by frontend for old backups
    lookup_id = batch_id
    if batch_id.startswith("legacy_"):
        lookup_id = batch_id[len("legacy_"):]

    try:
        target_date = datetime.strptime(lookup_id, "%Y-%m-%d").date()
        is_legacy = True
    except ValueError:
        is_legacy = False

    if is_legacy:
        backups = db.query(Backup).filter(func.date(Backup.timestamp) == target_date.isoformat()).all()
    else:
        backups = db.query(Backup).filter(Backup.batch_id == batch_id).all()
    
    if not backups:
        raise HTTPException(404, f"No backups found for batch {batch_id}")

    # Validation: Check if ANY backup in this batch/date is active or acknowledged
    for b in backups:
        dev = db.get(Device, b.device_id)
        if dev:
            if dev.active_backup_id == b.id or dev.last_ack_backup_id == b.id:
                raise HTTPException(403, f"Cannot delete batch {batch_id} because backup ID {b.id} is currently locked/active for device {dev.hostname}.")

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
    
    audit_event(user=current_user.username, action="backup_delete_batch", target=f"batch: {batch_id}", result=f"success (deleted {deleted_count} backups)")
    return {"message": f"Successfully deleted {deleted_count} backups for batch {batch_id}"}


@router.post("/acknowledge-all")
def acknowledge_all_backups(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """Acknowledge all changed backups (keep previous config as active reference, and clear 'Changed' status)."""
    devices = db.query(Device).filter(Device.enabled == True).all()
    count = 0
    for dev in devices:
        latest = (
            db.query(Backup)
            .filter(Backup.device_id == dev.id, Backup.status == "success")
            .order_by(Backup.timestamp.desc())
            .first()
        )
        if not latest:
            continue

        if dev.active_backup_id is None:
            active = latest
        else:
            active = db.get(Backup, dev.active_backup_id)
            if not active:
                active = latest

        # Check if it has a difference and is not acknowledged yet
        if active.id != latest.id and (not dev.last_ack_backup_id or dev.last_ack_backup_id != latest.id):
            if active.hash != latest.hash:
                dev.last_ack_backup_id = latest.id
                count += 1

    db.commit()
    
    audit_event(
        user=current_user.username,
        action="backup_acknowledge_all",
        target="all_devices",
        result=f"success (acknowledged {count} devices)"
    )
    return {"message": f"Successfully acknowledged {count} devices.", "count": count}


@router.post("/accept-latest-all")
def accept_latest_all_backups(current_user=Depends(require_admin), db: Session = Depends(get_db)):
    """Set the latest backup as the active reference for all changed devices."""
    devices = db.query(Device).filter(Device.enabled == True).all()
    count = 0
    for dev in devices:
        latest = (
            db.query(Backup)
            .filter(Backup.device_id == dev.id, Backup.status == "success")
            .order_by(Backup.timestamp.desc())
            .first()
        )
        if not latest:
            continue

        if dev.active_backup_id is None:
            active = latest
        else:
            active = db.get(Backup, dev.active_backup_id)
            if not active:
                active = latest

        # Check if it has a difference
        if active.id != latest.id:
            if active.hash != latest.hash:
                dev.active_backup_id = latest.id
                count += 1

    db.commit()
    
    audit_event(
        user=current_user.username,
        action="backup_accept_latest_all",
        target="all_devices",
        result=f"success (updated {count} devices)"
    )
    return {"message": f"Successfully updated {count} devices to latest backup.", "count": count}
