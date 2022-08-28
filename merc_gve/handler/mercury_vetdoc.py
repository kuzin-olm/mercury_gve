import re
import aioschedule

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from merc_gve.settings import logger, MERCURY_LOGIN, MERCURY_PASSWORD
from merc_gve.dto import User
from merc_gve.services.mercury.aioparser import VetRF
from merc_gve.services.telegram.states import VetdocPreParseState


__all__ = ["register_handlers_vetdoc_mercury"]


REGEX_DATE = r"^(0?[1-9]|[12][0-9]|3[01])[.](0?[1-9]|1[012])[.]\d{4}$"


def register_handlers_vetdoc_mercury(dispatcher: Dispatcher):
    dispatcher.register_message_handler(start_quiz_preparse, Text(equals="quiz", ignore_case=True))
    dispatcher.register_message_handler(date_validate, state=VetdocPreParseState.filter_date_start)
    dispatcher.register_message_handler(date_validate, state=VetdocPreParseState.filter_date_end)
    dispatcher.register_message_handler(fio_validate, state=VetdocPreParseState.filter_fio)
    dispatcher.register_callback_query_handler(cancel_quiz_preparse, text="stop", state=VetdocPreParseState)


async def start_quiz_preparse(message: types.Message):
    await message.answer(
        text="укажи с какой даты начать, н-р, 19.09.2009",
        reply_markup=get_cancel_inlinekeyboard(),
    )
    await VetdocPreParseState.filter_date_start.set()


async def date_validate(message: types.Message, state: FSMContext):
    date = message.text.strip()

    if re.search(REGEX_DATE, date):
        current_state = await state.get_state()

        if current_state == VetdocPreParseState.filter_date_start.state:
            text = "укажи до какой даты искать, н-р, 19.09.2009"
            await VetdocPreParseState.filter_date_end.set()
            await state.update_data({"date_start": date})
            await message.answer(text, reply_markup=get_cancel_inlinekeyboard())

        elif current_state == VetdocPreParseState.filter_date_end.state:
            text = "укажите ФИО через запятую"
            await VetdocPreParseState.filter_fio.set()
            await state.update_data({"date_end": date})
            await message.answer(text, reply_markup=get_cancel_inlinekeyboard())

        else:
            await message.answer("хмммм", reply_markup=get_cancel_inlinekeyboard())

    else:
        text = "упс, не правильная дата"
        await message.answer(text, reply_markup=get_cancel_inlinekeyboard())


async def fio_validate(message: types.Message, state: FSMContext):
    fio: list = message.text.strip().split(",")

    cleared_fio = [
        " ".join([name.strip().capitalize() for name in _fio.split()])
        for _fio in fio
    ]

    logger.debug(f"сырые: {fio}, обработанные: {cleared_fio}")

    fio_is_valid = all([len(_fio.split()) == 3 for _fio in cleared_fio])
    if fio_is_valid:
        await state.update_data({"fio": cleared_fio})

        user_data = await state.get_data()
        await state.finish()

        await message.answer("принял фио")
        # todo: в шедул завернуть - один хер - блокирует обычный реквест
        #       уйти на aiohttp ?
        # await run_parse_mercury_vet_doc(message=message, user_data=user_data)
        aioschedule.every().seconds.do(run_parse_mercury_vet_doc, message, user_data)
    else:
        text = "неправильно введены ФИО, н-р, список: \nфамилия имя отчество, фамилия имя отчество"
        await message.answer(text, reply_markup=get_cancel_inlinekeyboard())


async def cancel_quiz_preparse(query: types.CallbackQuery, state: FSMContext):
    text = "понял, принял"
    await query.answer(text)
    await query.bot.send_message(query.from_user.id, text)
    await state.finish()


async def run_parse_mercury_vet_doc(message: types.Message, user_data: dict):

    user = User(login=MERCURY_LOGIN, password=MERCURY_PASSWORD)
    mercury_gve = VetRF()

    is_auth = await mercury_gve.authenticate_by_login(login=user.login, password=user.password)

    if is_auth:
        try:
            await message.answer(text="начинаю собирать")
            vet_documents = await mercury_gve.run_parse_vetdocument(
                date_begin=user_data["date_start"],
                date_end=user_data["date_end"],
                filter_by_fio=user_data["fio"],
            )
            text_message = str(vet_documents[:1])
        except ValueError as err:
            text_message = str(err)
            logger.error(err)
        except Exception as err:
            text_message = "упс, что-то пошло не так"
            logger.error(err)

        await message.answer(text=text_message)

    else:
        await message.answer(text="не удалось авторизоваться")

    await mercury_gve.close()
    return aioschedule.CancelJob


def get_cancel_inlinekeyboard(text: str = "отмена") -> types.InlineKeyboardMarkup:
    keyboard_markup = types.InlineKeyboardMarkup()
    keyboard_markup.add(types.InlineKeyboardButton(text, callback_data="stop"))
    return keyboard_markup
