from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import SessionLocal
from ..models import Device, Backup
from ..schemas import DeviceIn, DeviceOut, TestResult
from ..utils.crypto import enc, dec
from ..services.netmiko_worker import fetch_running_config
from ..security import get_current_user, require_admin
from ..services.audit_log import audit_event

router = APIRouter(prefix="/devices", tags=["devices"])

def get_db(): 
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("", response_model=DeviceOut)
def create_device(payload: DeviceIn, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    dev = Device(
        hostname=payload.hostname, ip=payload.ip, vendor=payload.vendor,
        protocol=payload.protocol, port=payload.port,
        username_enc=enc(payload.username), password_enc=enc(payload.password),
        secret_enc=enc(payload.secret) if payload.secret else None, tags=payload.tags
    )
    db.add(dev); db.commit(); db.refresh(dev)
    audit_event(user=current_user.username, action="device_create", target=dev.hostname, result="success")
    return DeviceOut.model_validate(dev.__dict__)


@router.put("/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, payload: DeviceIn, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Not found")
    old_hostname = d.hostname
    d.hostname = payload.hostname
    d.ip = payload.ip
    d.vendor = payload.vendor
    d.protocol = payload.protocol
    d.port = payload.port
    if payload.username:
        d.username_enc = enc(payload.username)
    if payload.password:
        d.password_enc = enc(payload.password)
    d.secret_enc = enc(payload.secret) if payload.secret else None
    d.tags = payload.tags
    if payload.enabled is not None:
        d.enabled = payload.enabled
    db.commit(); db.refresh(d)
    audit_event(user=current_user.username, action="device_update", target=old_hostname, result="success")
    return DeviceOut.model_validate(d.__dict__)


@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Not found")
    hostname = d.hostname
    db.delete(d); db.commit()
    audit_event(user=current_user.username, action="device_delete", target=hostname, result="success")
    return {"deleted": True}

@router.get("", response_model=list[DeviceOut])
def list_devices(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Get all devices
    devices = db.query(Device).all()
    
    # 2. Get latest backup timestamp per device
    latest_backups_query = db.query(Backup.device_id, func.max(Backup.timestamp)).group_by(Backup.device_id).all()
    backup_map = {device_id: timestamp for device_id, timestamp in latest_backups_query}

    # 3. Merge data
    results = []
    for d in devices:
        # Create a dictionary from the model instance
        d_dict = {c.name: getattr(d, c.name) for c in d.__table__.columns}
        # Add the last_backup field
        d_dict['last_backup'] = backup_map.get(d.id)
        results.append(DeviceOut.model_validate(d_dict))
    
    return results

@router.get("/tags/available")
def get_available_tags(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all unique tags used across all devices"""
    devices = db.query(Device).all()
    tags_set = set()
    for d in devices:
        if d.tags:
            for tag in d.tags.split(","):
                tag = tag.strip()
                if tag:
                    tags_set.add(tag)
    return {"tags": sorted(list(tags_set))}

@router.post("/{device_id}/test", response_model=TestResult)
def test_device(device_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    d = db.get(Device, device_id)
    if not d: raise HTTPException(404, "Not found")
    try:
        decrypted_user = dec(d.username_enc)
        decrypted_pass = dec(d.password_enc)
        decrypted_secret = dec(d.secret_enc) if d.secret_enc else None
        
        fetch_running_config(
            vendor=d.vendor, host=d.ip, username=decrypted_user,
            password=decrypted_pass, secret=decrypted_secret,
            protocol=d.protocol, port=d.port, cmd="show version"
        )
        audit_event(user=current_user.username, action="device_test", target=d.hostname, result="success")
        return TestResult(success=True, message="OK")
    except Exception as e:
        audit_event(user=current_user.username, action="device_test", target=d.hostname, result=f"failed: {str(e)}")
        return TestResult(success=False, message=f"Failed: {e}")
