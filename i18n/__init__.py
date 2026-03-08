"""Localization: t(key, locale) returns string by key and locale (ru/en)."""
from typing import Dict

from i18n.ru import RU
from i18n.en import EN

_LOCALES: Dict[str, Dict[str, str]] = {"ru": RU, "en": EN}
_DEFAULT = "ru"


def t(key: str, locale: str = None, **kwargs) -> str:
    """Get localized string by key and locale. Use {placeholder} in key value, pass kwargs to format."""
    loc = (locale or _DEFAULT).lower()
    if loc not in _LOCALES:
        loc = _DEFAULT
    s = _LOCALES[loc].get(key) or _LOCALES[_DEFAULT].get(key) or key
    if kwargs:
        try:
            return s.format(**kwargs)
        except KeyError:
            return s
    return s
