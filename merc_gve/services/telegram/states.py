from aiogram.dispatcher.filters.state import State, StatesGroup


class CreateTaskState(StatesGroup):
    period = State()
