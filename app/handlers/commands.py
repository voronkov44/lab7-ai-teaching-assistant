from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Привет! 👋\n\n"
        "Это учебный бот для автоматической обработки "
        "обращений студентов с помощью ИИ.\n\n"
        "Отправь текстовое обращение. "
        "Оно будет сохранено в PostgreSQL "
        "и автоматически проанализировано нейросетью.\n\n"
        "Результаты обработки сохраняются в базе данных.\n\n"
        "Используй только тестовые данные."
    )
