"""Feed service: Haversine distance, format distance for display, gender emoji."""
import math
from typing import Optional, Tuple

from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Like


def gender_emoji(gender: Optional[str]) -> str:
    """Один нейтральный эмодзи пола рядом с именем/возрастом: голубой — мужской, розовый — женский."""
    s = (gender or "").strip().upper()
    if not s:
        return "⚪"
    c = s[0]
    if c in ("M", "М"):
        return "🔵"
    if c in ("F", "Ж"):
        return "💗"
    return "⚪"


# Earth radius in km
EARTH_RADIUS_KM = 6371.0


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distance in km between two points (Haversine)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(min(1.0, a)))
    return EARTH_RADIUS_KM * c


def format_distance_km(km: float, locale: str = "ru") -> str:
    """Format distance for card: ~N km or 'менее 5 км' / 'under 5 km'."""
    from i18n import t
    if km < 5:
        return t("feed_distance_lt5", locale)
    return t("feed_distance_km", locale, km=round(km))
