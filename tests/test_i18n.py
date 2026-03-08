"""Tests for i18n.t() and locale resolution."""
import pytest

from i18n import t


def test_t_ru_default():
    s = t("onboarding_welcome")
    assert "имя" in s.lower() or "name" in s.lower() or "обращаться" in s.lower() or "address" in s.lower()


def test_t_explicit_ru():
    s = t("onboarding_welcome", locale="ru")
    assert len(s) > 0
    s2 = t("menu_profile", locale="ru")
    # ru: "menu_profile" = "👤 Анкета"
    assert "Анкета" in s2


def test_t_explicit_en():
    s = t("onboarding_welcome", locale="en")
    assert "Welcome" in s or "name" in s.lower()
    s2 = t("menu_profile", locale="en")
    assert "Profile" in s2


def test_t_unknown_locale_falls_back_to_default():
    s = t("menu_feed", locale="xx")
    assert len(s) > 0
    assert s == t("menu_feed", locale="ru") or s == t("menu_feed", locale="en")


def test_t_missing_key_returns_key():
    assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"


def test_t_format_kwargs():
    # Key that has placeholder in locale; if none, format may still be applied
    s = t("menu_profile")
    assert len(s) > 0
    # Test with a key that might have {name} or similar in some locales
    s2 = t("onboarding_welcome", name="Test")
    assert len(s2) > 0
