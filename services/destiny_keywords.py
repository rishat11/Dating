"""Keyword phrases and weights for MVP destiny index (lexical level)."""
# Категории и примеры фраз с весами (в процентах к индексу)
# Веса заданы как целые числа; при расчёте делим на 100 или нормируем.

KEYWORD_CATEGORIES = {
    "common_interests": {
        "weight": 3,
        "phrases": [
            "тоже люблю", "я тоже", "обожаю этот фильм", "мой любимый сериал",
            "тоже самое", "мы похожи", "одинаково", "как и я", "тоже нравится",
            "общие интересы", "у нас общее", "совпало",
        ],
    },
    "deep_topics": {
        "weight": 5,
        "phrases": [
            "философия", "смысл жизни", "страхи", "детство", "отношения",
            "мечта", "цель в жизни", "что для тебя важно", "веришь ли",
            "думаешь о", "мечтаешь", "боюсь что",
        ],
    },
    "humor": {
        "weight": 2,
        "phrases": [
            "лол", "ахаха", "хаха", "смешно", "прикол", "шутка", "угар",
            "ржачно", "умираю", "убил", "красавчик",
        ],
    },
    "compliments": {
        "weight": 2,
        "phrases": [
            "ты классная", "красивая", "умная", "прикольный", "крутой",
            "ты молодец", "супер", "здорово", "мне нравишься", "класс",
            "отличный", "замечательный", "прелесть",
        ],
    },
    "music_movies": {
        "weight": 3,
        "phrases": [
            "люблю музыку", "любимый фильм", "сериал", "группа", "исполнитель",
            "трек", "альбом", "смотрю", "слушаю", "рекомендую посмотреть",
            "рекомендую послушать",
        ],
    },
}


def calc_lexical_bonus(text: str) -> float:
    """Return bonus percent (0..~15) for one message based on keywords."""
    if not text or not text.strip():
        return 0.0
    t = text.lower().strip()
    total = 0.0
    for cat, data in KEYWORD_CATEGORIES.items():
        w = data["weight"]
        for phrase in data["phrases"]:
            if phrase in t:
                total += w * 0.3  # cap per category
                break
    return min(total, 7.0)  # max ~7% per message from keywords
