from ..database import SessionLocal
from ..models import Audit
from ..utils.timeutil import tznow
import logging

logger = logging.getLogger(__name__)


def audit_event(user: str, action: str, target: str, result: str):
    """
    Log an audit event to the database.
    
    Args:
        user: Username performing the action (or 'system')
        action: Action type (e.g., 'login', 'device_create', 'job_run')
        target: Target of the action (device name, user name, job id, etc.)
        result: Result of the action ('success' or error message)
    """
    db = SessionLocal()
    try:
        a = Audit(
            user=user,
            action=action,
            target=target,
            result=result,
            timestamp=tznow()
        )
        db.add(a)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
    finally:
        db.close()
