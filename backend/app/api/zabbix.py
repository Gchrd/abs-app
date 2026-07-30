import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import Device
from ..security import require_admin
from ..services import zabbix_client
from ..services.zabbix_client import ZabbixNotConfigured, ZabbixError

router = APIRouter(prefix="/zabbix", tags=["zabbix"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SyncRequest(BaseModel):
    group_ids: list[str]


PORTS_TO_CHECK = [22, 23]


async def _port_open(ip: str, port: int, timeout: float = 3.0) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _check_host(candidate: dict) -> dict | None:
    ip = candidate["ip"]
    results = await asyncio.gather(*(_port_open(ip, p) for p in PORTS_TO_CHECK))
    open_ports = [p for p, ok in zip(PORTS_TO_CHECK, results) if ok]
    if not open_ports:
        return None
    return {"hostname": candidate["hostname"], "ip": ip, "open_ports": open_ports}


@router.get("/host-groups")
def get_host_groups(current_user=Depends(require_admin)):
    try:
        return zabbix_client.list_host_groups()
    except ZabbixNotConfigured as e:
        raise HTTPException(503, str(e))
    except ZabbixError as e:
        raise HTTPException(502, f"Zabbix error: {e}")
    except Exception as e:
        raise HTTPException(502, f"Failed to reach Zabbix: {e}")


@router.post("/sync")
async def sync_devices(payload: SyncRequest, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    if not payload.group_ids:
        raise HTTPException(400, "group_ids is required")

    try:
        hosts = zabbix_client.list_hosts_in_groups(payload.group_ids)
    except ZabbixNotConfigured as e:
        raise HTTPException(503, str(e))
    except ZabbixError as e:
        raise HTTPException(502, f"Zabbix error: {e}")
    except Exception as e:
        raise HTTPException(502, f"Failed to reach Zabbix: {e}")

    existing_ips = {ip for (ip,) in db.query(Device.ip).all()}
    candidates = [h for h in hosts if h["ip"] not in existing_ips]

    checked = await asyncio.gather(*(_check_host(c) for c in candidates))
    reachable = [c for c in checked if c is not None]

    return {"candidates": reachable, "checked": len(candidates), "skipped_existing": len(hosts) - len(candidates)}
