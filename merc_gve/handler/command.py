from aiogram import types, Dispatcher


__all__ = ['register_handlers_command']


def register_handlers_command(dispatcher: Dispatcher):
    dispatcher.register_message_handler(start, commands=["start", "help"])


async def start(message: types.Message):
    keyboard_markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)

    btns_text = ("проверить", "периодически", "остановить")
    keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text))

    await message.reply("Здарова, бандит!", reply_markup=keyboard_markup)
