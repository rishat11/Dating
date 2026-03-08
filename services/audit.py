"""Structured audit log: match create, block, report, chat end. No message bodies."""
import logging
import json
from datetime import datetime
from typing import Optional

logger = logging.getLogger("audit")
# Ensure handler only if needed
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)


def _event(action: str, user_id: Optional[int] = None, match_id: Optional[int] = None, **kwargs) -> None:
    payload = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "user_id": user_id,
        "match_id": match_id,
        **{k: v for k, v in kwargs.items() if v is not None},
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def audit_match_created(match_id: int, user_1_id: int, user_2_id: int) -> None:
    _event("match_created", match_id=match_id, user_1_id=user_1_id, user_2_id=user_2_id)


def audit_block(match_id: int, user_id: int, blocked_by_id: int) -> None:
    _event("block", match_id=match_id, user_id=user_id, blocked_by_id=blocked_by_id)


def audit_report(match_id: int, user_id: int, reported_by_id: int) -> None:
    _event("report", match_id=match_id, user_id=user_id, reported_by_id=reported_by_id)


def audit_chat_ended(match_id: int, user_id: int) -> None:
    _event("chat_ended", match_id=match_id, user_id=user_id)


def audit_message_rejected_contact(match_id: int, user_id: int, message_id: Optional[int] = None, length: Optional[int] = None) -> None:
    _event("message_rejected_contact", match_id=match_id, user_id=user_id, message_id=message_id, length=length)
