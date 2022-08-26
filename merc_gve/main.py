from settings import API_TG_BOT

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from merc_gve.services.telegram.task import run_schedule_handler
from merc_gve.handler import register_handlers_command, register_handlers_checked_mercury, \
    register_handlers_vetdoc_mercury


def setup_handlers(dispatcher: Dispatcher):
    register_handlers_command(dispatcher)
    register_handlers_checked_mercury(dispatcher)
    register_handlers_vetdoc_mercury(dispatcher)


def main():
    bot = Bot(token=API_TG_BOT)
    storage = MemoryStorage()

    dp = Dispatcher(bot, storage=storage)
    setup_handlers(dispatcher=dp)

    executor.start_polling(dp, skip_updates=True, on_startup=run_schedule_handler)


if __name__ == "__main__":
    main()
