"""Check message text for contact-sharing patterns (phone, vk.com, t.me/username)."""
import re
from typing import Tuple

# Simple patterns: phone (RU/international), vk.com, t.me/username, instagram, etc.
PHONE_PATTERN = re.compile(
    r"\+?[78][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}|\d{10,11}"
)
VK_PATTERN = re.compile(r"vk\.com/[\w.]+\b", re.I)
TG_PATTERN = re.compile(r"t\.me/[\w]+\b", re.I)
INSTA_PATTERN = re.compile(r"instagram\.com/[\w.]+\b", re.I)


def has_contact_markers(text: str) -> bool:
    """Return True if text contains phone, vk, t.me, instagram links."""
    if not text or not text.strip():
        return False
    t = text.strip()
    if PHONE_PATTERN.search(t):
        return True
    if VK_PATTERN.search(t):
        return True
    if TG_PATTERN.search(t):
        return True
    if INSTA_PATTERN.search(t):
        return True
    return False


def replace_contact_markers(text: str) -> str:
    """Replace contact markers with [скрыто] for sending to partner (optional use)."""
    if not text:
        return text
    t = PHONE_PATTERN.sub("[скрыто]", text)
    t = VK_PATTERN.sub("[скрыто]", t)
    t = TG_PATTERN.sub("[скрыто]", t)
    t = INSTA_PATTERN.sub("[скрыто]", t)
    return t
