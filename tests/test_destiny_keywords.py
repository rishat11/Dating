"""Tests for services.destiny_keywords (calc_lexical_bonus, KEYWORD_CATEGORIES)."""
import pytest

from services.destiny_keywords import KEYWORD_CATEGORIES, calc_lexical_bonus


def test_calc_lexical_bonus_empty():
    assert calc_lexical_bonus("") == 0.0
    assert calc_lexical_bonus("   ") == 0.0
    assert calc_lexical_bonus("\n\t") == 0.0


def test_calc_lexical_bonus_no_keywords():
    assert calc_lexical_bonus("привет как дела") == 0.0
    assert calc_lexical_bonus("hello world") == 0.0


def test_calc_lexical_bonus_single_phrase():
    # "тоже люблю" in common_interests (weight 3)
    b = calc_lexical_bonus("я тоже люблю кофе")
    assert b > 0
    assert b <= 7.0


def test_calc_lexical_bonus_multiple_categories():
    text = "обожаю этот фильм и философия смысл жизни лол"
    b = calc_lexical_bonus(text)
    assert b > 0
    assert b <= 7.0


def test_calc_lexical_bonus_cap_per_message():
    # Many phrases should still cap at 7.0
    parts = [
        "тоже люблю", "философия", "лол", "ты классная", "люблю музыку",
        "общие интересы", "мечта", "хаха", "красивая", "сериал",
    ]
    text = " ".join(parts)
    b = calc_lexical_bonus(text)
    assert b <= 7.0


def test_keyword_categories_structure():
    for cat, data in KEYWORD_CATEGORIES.items():
        assert "weight" in data
        assert "phrases" in data
        assert isinstance(data["weight"], (int, float))
        assert isinstance(data["phrases"], list)
        assert len(data["phrases"]) > 0
