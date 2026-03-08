"""
Проверка, что все зарегистрированные хендлеры и их фильтры имеют callable callback
и что при разрешении фильтров не возникает TypeError (например F | Command -> bool | Command).

Почему обычные тесты это не ловили:
- Существующие тесты не поднимают диспетчер и не обрабатывают апдейты: они проверяют
  только config, models, i18n, middleware (с моками), rate_limit, destiny_keywords.
- Ошибка «TypeError: the first argument must be callable» возникает в рантайме при
  обработке апдейта, когда диспетчер вызывает handler.check() -> event_filter.call() ->
  partial(self.callback, ...). Если callback у фильтра не callable (например кортеж
  состояний или объект Handler из-за двух декораторов), падает только в этот момент.
- Ошибка «unsupported operand type(s) for |: 'bool' and 'Command'» возникает при
  разрешении комбинации MagicFilter | Command в magic_filter: левая часть даёт bool,
  правая — объект Command, и операция | не поддерживается.

Этот тест обходит все роутеры после setup_routers() и проверяет статически: у каждого
HandlerObject callback callable и у каждого FilterObject callback callable; плюс
проверяет вызов каждого фильтра с мок-событием (без TypeError на | и bool/Command).
"""
from unittest.mock import MagicMock

import pytest

from handlers import setup_routers


def _collect_routers(router, seen=None):
    if seen is None:
        seen = set()
    if id(router) in seen:
        return []
    seen.add(id(router))
    result = [router]
    for sub in getattr(router, "sub_routers", []) or []:
        result.extend(_collect_routers(sub, seen))
    return result


@pytest.fixture(scope="module")
def _router_root():
    """Один раз поднимаем роутеры (повторный вызов setup_routers() ломает привязку)."""
    return setup_routers()


@pytest.fixture(scope="module")
def all_handlers_and_filters(_router_root):
    """Собираем все хендлеры и их фильтры из _router_root."""
    routers = _collect_routers(_router_root)
    out = []
    for r in routers:
        for obs in (r.observers or {}).values():
            handlers = getattr(obs, "handlers", None) or []
            for h in handlers:
                out.append((h, getattr(h, "filters", []) or []))
    return out


@pytest.fixture(scope="module")
def all_handlers_with_event_name(_router_root):
    """Собираем (event_name, handler, filters) для вызова фильтров с правильным мок-событием."""
    routers = _collect_routers(_router_root)
    out = []
    for r in routers:
        for event_name, obs in (r.observers or {}).items():
            handlers = getattr(obs, "handlers", None) or []
            for h in handlers:
                filters = getattr(h, "filters", None) or []
                out.append((event_name, h, filters))
    return out


def test_all_handler_callbacks_are_callable(all_handlers_and_filters):
    """У каждого зарегистрированного хендлера callback должен быть callable."""
    for handler, _ in all_handlers_and_filters:
        assert callable(
            getattr(handler, "callback", None)
        ), f"Handler callback must be callable, got {type(handler.callback).__name__}: {handler.callback!r}"


def test_all_filter_callbacks_are_callable(all_handlers_and_filters):
    """У каждого фильтра хендлера callback должен быть callable (иначе partial(...) падает при обработке апдейта)."""
    for handler, filters in all_handlers_and_filters:
        for i, f in enumerate(filters):
            cb = getattr(f, "callback", None)
            assert callable(
                cb
            ), (
                f"Filter #{i} of handler {getattr(handler.callback, '__name__', handler.callback)} must have callable callback, "
                f"got {type(cb).__name__}: {cb!r}"
            )


def _make_mock_event(event_name: str):
    """Минимальный мок события для вызова фильтров (message / callback_query)."""
    if event_name == "message":
        ev = MagicMock()
        ev.text = "test"
        ev.photo = None
        ev.location = None
        ev.voice = None
        ev.sticker = None
        ev.from_user = MagicMock()
        ev.from_user.id = 1
        return ev
    if event_name == "callback_query":
        ev = MagicMock()
        ev.data = "test:value"
        ev.message = MagicMock()
        ev.from_user = MagicMock()
        ev.from_user.id = 1
        return ev
    return MagicMock()


@pytest.mark.asyncio
async def test_filter_resolve_no_bool_or_command_type_error(all_handlers_with_event_name):
    """При разрешении фильтров не должно возникать TypeError: unsupported operand type(s) for |: 'bool' and 'Command'.
    Такая ошибка была при комбинации F.text.in_(...) | Command(...) в одном декораторе."""
    kwargs = {"raw_state": None, "bot": MagicMock()}
    for event_name, handler, filters in all_handlers_with_event_name:
        event = _make_mock_event(event_name)
        for i, event_filter in enumerate(filters):
            try:
                await event_filter.call(event, **kwargs)
            except TypeError as e:
                if "unsupported operand type(s) for |" in str(e) and ("bool" in str(e) or "Command" in str(e)):
                    pytest.fail(
                        f"Filter #{i} of handler {getattr(handler.callback, '__name__', handler.callback)} "
                        f"(event={event_name}) raised: {e}. "
                        "Do not combine MagicFilter (F) with Command using |; use two @router.message(...) decorators instead."
                    )
                raise
