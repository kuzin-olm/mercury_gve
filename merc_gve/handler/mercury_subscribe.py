import asyncio
import aioschedule
from datetime import datetime

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from merc_gve.settings import logger, MERCURY_LOGIN, MERCURY_PASSWORD
from merc_gve.dto import User
from merc_gve.types import NotificationType
from merc_gve.services.mercury.parser import VetRF
from merc_gve.services.telegram.message_maker import make_answer_by_enterprises
from merc_gve.services.telegram.task import add_task_by_minutes, get_user_tasks
from merc_gve.services.telegram.states import CreateTaskState


__all__ = ['register_handlers_checked_mercury']


def register_handlers_checked_mercury(dispatcher: Dispatcher):
    # одиночный вызов
    dispatcher.register_message_handler(send_checked_mercury_notified, Text(equals="проверить", ignore_case=True))

    # управление отложенным вызовом
    dispatcher.register_message_handler(create_schedule_task, Text(equals="периодически", ignore_case=True))
    dispatcher.register_message_handler(choose_period_schedule_task, state=CreateTaskState.period)
    dispatcher.register_callback_query_handler(choose_period_schedule_task_callback_handler,
                                               text='5', state=CreateTaskState.period)
    dispatcher.register_callback_query_handler(choose_period_schedule_task_callback_handler,
                                               text='10', state=CreateTaskState.period)
    dispatcher.register_callback_query_handler(choose_period_schedule_task_callback_handler,
                                               text='30', state=CreateTaskState.period)
    dispatcher.register_callback_query_handler(choose_period_schedule_task_callback_handler,
                                               text='stop', state=CreateTaskState.period)
    dispatcher.register_message_handler(cancel_schedule_task, Text(equals="остановить", ignore_case=True))


async def send_checked_mercury_notified(message: types.Message, is_schedule: bool = False):
    enterprises = []

    user = User(login=MERCURY_LOGIN, password=MERCURY_PASSWORD)
    mercury_gve = VetRF()

    is_auth = mercury_gve.authenticate_by_login(login=user.login, password=user.password)

    if is_auth:
        try:
            enterprises = mercury_gve.get_notify_enterprises(
                parents=['ООО "Русь"'],
                types=[NotificationType.HS],
            )
            messages = make_answer_by_enterprises(enterprises=enterprises)
        except Exception as err:
            messages = ["упс, что-то пошло не так"]
            logger.error(err)

        silent: bool = 0 < datetime.now().hour < 8

        if is_schedule and not enterprises:
            pass
        else:
            try:
                for text_message in messages:
                    await message.answer(
                        text=text_message,
                        parse_mode=types.ParseMode.HTML,
                        disable_notification=silent,
                    )
                    await asyncio.sleep(1)
            except Exception as err:
                logger.error(err)
    else:
        await message.answer(
            text="сессия не прошла авторизацию",
            parse_mode=types.ParseMode.HTML,
        )


async def create_schedule_task(message: types.Message):
    user_tasks = get_user_tasks(user_id=message.from_user.id)

    if user_tasks:
        logger.debug(f"{message.from_user.id} уже есть в евент залупе")
        await message.answer("уже запущено")

    else:
        keyboard_markup = types.InlineKeyboardMarkup(row_width=3)

        text_and_data = (
            ('5 минут', '5'),
            ('10 минут', '10'),
            ('30 минут', '30'),
        )
        row_btns = (types.InlineKeyboardButton(text, callback_data=data) for text, data in text_and_data)
        keyboard_markup.row(*row_btns)
        keyboard_markup.add(
            types.InlineKeyboardButton("отмена", callback_data="stop"),
        )
        await message.answer(
            text="с какой периодичностью проверять?\nвыбери или напиши сам минуты",
            reply_markup=keyboard_markup,
        )
        await CreateTaskState.period.set()


async def choose_period_schedule_task(message: types.Message, state: FSMContext):
    try:
        period = int(message.text)
        await add_task_by_minutes(period_minutes=period, func=send_checked_mercury_notified, params=[message, True])
        await message.answer(f"запущено с периодичностью: {period} минут")
        await state.finish()
    except (TypeError, ValueError):
        keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
        keyboard_markup.add(
            types.InlineKeyboardButton("отмена", callback_data="stop"),
        )
        await message.answer("необходимо ввести число", reply_markup=keyboard_markup)


async def choose_period_schedule_task_callback_handler(query: types.CallbackQuery, state: FSMContext):
    answer_data = query.data

    if answer_data == 'stop':
        text = "понял"
        await query.answer(text)
        await query.bot.send_message(query.from_user.id, text)

        await state.finish()
        return

    try:
        period = int(answer_data)
        await add_task_by_minutes(period_minutes=period, func=send_checked_mercury_notified, params=[query, True])

        text = f"запущено с периодичностью: {period} минут"
        await query.answer(text)
        await query.bot.send_message(query.from_user.id, text)

        await state.finish()

    except (TypeError, ValueError):
        text = "необходимо ввести число"
        await query.answer(text)
        await query.bot.send_message(query.from_user.id, text)


async def cancel_schedule_task(message: types.Message):
    user_tasks = get_user_tasks(user_id=message.from_user.id)

    if user_tasks:
        [aioschedule.jobs.remove(_task) for _task in user_tasks]
        await message.answer("остановлено")

    else:
        logger.debug(f"нет такой таски: {message.from_user.id}")
        await message.answer("нет запущенных тасок")
