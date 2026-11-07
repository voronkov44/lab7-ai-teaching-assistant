from aiogram import F, Router
from aiogram.types import Message

from app.services.processor import ProcessingService

router = Router()


@router.message(F.chat.type == "private", F.text)
async def incoming_text(
    message: Message,
    processor: ProcessingService,
) -> None:
    if message.text.startswith("/"):
        return

    await processor.receive_message(
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        message_id=message.message_id,
        text=message.text,
    )
