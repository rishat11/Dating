"""Tests for db.models: User, Match, enums, helper methods."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from db.models import (
    Base,
    Gender,
    MatchStatus,
    MessageType,
    User,
    Like,
    Match,
    Message,
    DestinyIndex,
    DestinyEvent,
)


def test_gender_enum():
    assert Gender.M.value == "M"
    assert Gender.F.value == "F"
    assert Gender.OTHER.value == "other"


def test_match_status_enum():
    assert MatchStatus.ACTIVE.value == "active"
    assert MatchStatus.BLOCKED.value == "blocked"
    assert MatchStatus.ENDED.value == "ended"


def test_message_type_enum():
    assert MessageType.TEXT.value == "text"
    assert MessageType.PHOTO.value == "photo"


def test_user_is_registered_false():
    u = User(
        telegram_id=1,
        first_name="Test",
        age_confirmed_18=False,
        rules_accepted=False,
    )
    assert u.is_registered() is False
    u.age_confirmed_18 = True
    assert u.is_registered() is False
    u.rules_accepted = True
    assert u.is_registered() is True


def test_user_is_registered_true():
    u = User(
        telegram_id=1,
        first_name="Test",
        age_confirmed_18=True,
        rules_accepted=True,
    )
    assert u.is_registered() is True


def test_user_is_profile_filled_false():
    u = User(telegram_id=1, first_name="A", profile_filled=False)
    assert u.is_profile_filled() is False
    u.profile_filled = True
    assert u.is_profile_filled() is False
    u.display_name = "Alice"
    u.age = 25
    u.gender = "F"
    u.looking_for = "M"
    assert u.is_profile_filled() is False
    u.profile_photo_file_id = "file_123"
    assert u.is_profile_filled() is True


def test_user_is_profile_filled_true():
    u = User(
        telegram_id=1,
        first_name="A",
        profile_filled=True,
        display_name="Bob",
        age=30,
        gender="M",
        looking_for="F",
        profile_photo_file_id="file_1",
    )
    assert u.is_profile_filled() is True


def test_match_partner_of():
    u1 = User(telegram_id=10, first_name="U1")
    u2 = User(telegram_id=20, first_name="U2")
    u1.id = 1
    u2.id = 2
    m = Match(user_1_id=1, user_2_id=2, user_1=u1, user_2=u2)
    assert m.partner_of(10) is None  # telegram_id not user_id
    assert m.partner_of(1) is u2
    assert m.partner_of(2) is u1
    assert m.partner_of(99) is None


def test_match_other_user_id():
    m = Match(user_1_id=1, user_2_id=2)
    assert m.other_user_id(1) == 2
    assert m.other_user_id(2) == 1
