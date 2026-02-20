from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .utils.timeutil import tznow
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=tznow)

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hostname: Mapped[str] = mapped_column(String(128), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    vendor: Mapped[str] = mapped_column(String(64))
    protocol: Mapped[str] = mapped_column(String(16))  # SSH/Telnet
    port: Mapped[int] = mapped_column(Integer, default=22)
    username_enc: Mapped[str] = mapped_column(Text)  # terenkripsi
    password_enc: Mapped[str] = mapped_column(Text)
    secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str | None] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    active_backup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # FK ke backups.id (plain int, hindari circular FK)
    last_ack_backup_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # ID backup terbaru yang sudah di-acknowledge admin

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    triggered_by: Mapped[str] = mapped_column(String(64))  # manual/schedule:Name
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/success/failed/queued
    started_at: Mapped[datetime] = mapped_column(DateTime, default=tznow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    devices: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[str | None] = mapped_column(Text)

class Backup(Base):
    __tablename__ = "backups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=tznow)
    size_bytes: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="success")
    path: Mapped[str] = mapped_column(String(512))

class Schedule(Base):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=7)
    run_at: Mapped[str] = mapped_column(String(5), default="02:00")  # HH:MM
    target_type: Mapped[str] = mapped_column(String(32), default="All")  # All/Tag/Devices
    target_tags: Mapped[str | None] = mapped_column(String(256), nullable=True)  # comma-separated tags
    retention: Mapped[int] = mapped_column(Integer, default=10)
    notify_on_fail: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=tznow)
    user: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(256))
    result: Mapped[str] = mapped_column(String(16))
