"""FSM states for onboarding, profile, chat."""
from aiogram.fsm.state import State, StatesGroup


class OnboardingState(StatesGroup):
    name = State()
    photo = State()
    birth_date = State()
    age_confirm = State()
    rules_accept = State()
    language = State()


class ProfileState(StatesGroup):
    display_name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    photo = State()
    description = State()
    interests = State()
    movies_music = State()
    zodiac = State()
    confirm = State()


class ChatState(StatesGroup):
    in_chat = State()
