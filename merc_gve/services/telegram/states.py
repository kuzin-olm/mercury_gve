from aiogram.dispatcher.filters.state import State, StatesGroup


class CreateTaskState(StatesGroup):
    period = State()


class VetdocPreParseState(StatesGroup):
    filter_date_start = State()
    filter_date_end = State()
    filter_fio = State()
