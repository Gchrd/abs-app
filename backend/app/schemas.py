from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DeviceIn(BaseModel):
    hostname: str
    ip: str
    vendor: str
    protocol: str = "SSH"
    port: int = 22
    username: str
    password: str
    secret: Optional[str] = None
    tags: Optional[str] = None
    enabled: Optional[bool] = None


class DeviceOut(BaseModel):
    id: int
    hostname: str
    ip: str
    vendor: str
    protocol: str
    port: int
    tags: Optional[str] = None
    enabled: bool = True
    last_backup: Optional[datetime] = None


class TestResult(BaseModel):
    success: bool
    message: str


# --- Users ---
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime


# --- Schedules ---
class ScheduleIn(BaseModel):
    name: Optional[str] = None
    device_id: Optional[int] = None
    schedule_time: str  # HH:MM
    enabled: bool = True
    interval_days: Optional[int] = None
    target_type: Optional[str] = None  # All/Tag/Devices
    target_tags: Optional[str] = None  # comma-separated tags for Tag type


class ScheduleOut(BaseModel):
    id: int
    name: str
    run_at: str
    enabled: bool
    interval_days: int
    target_type: str
    target_tags: Optional[str] = None
    retention: int
    notify_on_fail: bool


# --- Audit ---
class AuditOut(BaseModel):
    id: int
    timestamp: datetime
    user: str
    action: str
    target: str
    result: str

