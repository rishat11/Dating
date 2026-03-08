"""FSM states for onboarding, profile, chat."""
from aiogram.fsm.state import State, StatesGroup


class OnboardingState(StatesGroup):
    birth_date = State()
    age_confirm = State()
    rules_accept = State()
    language = State()


class ProfileState(StatesGroup):
    choose_field = State()
    display_name = State()
    gender = State()
    looking_for = State()
    city = State()
    photo = State()
    description = State()
    interests = State()
    movies = State()
    series = State()
    music = State()
    confirm = State()


class ChatState(StatesGroup):
    in_chat = State()
