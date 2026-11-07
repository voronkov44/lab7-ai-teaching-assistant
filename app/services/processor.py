from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.adapters.database import Analysis, Request
from app.adapters.ollama import OllamaClient

logger = logging.getLogger(__name__)


class ProcessingService:
    def __init__(
        self,
        *,
        sessions: async_sessionmaker,
        ollama: OllamaClient,
    ):
        self.sessions = sessions
        self.ollama = ollama

    async def receive_message(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        message_id: int,
        text: str,
    ) -> int | None:
        # Сначала сохраняем сообщение в БД, затем вызываем ИИ.
        async with self.sessions.begin() as session:
            statement = (
                insert(Request)
                .values(
                    telegram_chat_id=chat_id,
                    telegram_user_id=user_id,
                    telegram_message_id=message_id,
                    text=text,
                    status="new",
                )
                .on_conflict_do_nothing(
                    constraint="uq_request_telegram_message"
                )
                .returning(Request.id)
            )
            request_id = await session.scalar(statement)

        if request_id is None:
            logger.info(
                "Duplicate Telegram message ignored: "
                "chat_id=%s message_id=%s",
                chat_id,
                message_id,
            )
            return None

        logger.info(
            "request=%s saved to PostgreSQL status=new",
            request_id,
        )

        await self.process_request(request_id)
        return request_id

    async def process_request(self, request_id: int) -> None:
        async with self.sessions.begin() as session:
            request = await session.get(Request, request_id)

            if request is None or request.status != "new":
                return

            question = request.text
            request.status = "processing"

        logger.info(
            "request=%s -> Ollama model=%s",
            request_id,
            self.ollama.model,
        )

        started = perf_counter()

        try:
            result, raw_response = await self.ollama.analyze(
                question
            )
            duration_ms = int(
                (perf_counter() - started) * 1000
            )

            async with self.sessions.begin() as session:
                session.add(
                    Analysis(
                        request_id=request_id,
                        model_name=self.ollama.model,
                        category=result.category,
                        summary=result.summary,
                        requires_review=result.requires_review,
                        review_reason=result.review_reason,
                        raw_response=raw_response,
                        duration_ms=duration_ms,
                    )
                )

                request = await session.get(Request, request_id)
                request.status = "processed"
                request.processed_at = datetime.now(timezone.utc)
                request.error_message = None

            logger.info(
                "request=%s processed in %d ms | "
                "category=%s | requires_review=%s | "
                "reason=%s | summary=%s",
                request_id,
                duration_ms,
                result.category,
                result.requires_review,
                result.review_reason,
                result.summary,
            )

        except Exception as exc:
            logger.exception(
                "request=%s failed",
                request_id,
            )

            async with self.sessions.begin() as session:
                request = await session.get(Request, request_id)

                if request is not None:
                    request.status = "failed"
                    request.error_message = str(exc)[:1000]

    async def process_new_on_startup(self) -> None:
        async with self.sessions() as session:
            ids = list(
                await session.scalars(
                    select(Request.id)
                    .where(Request.status == "new")
                    .order_by(Request.id)
                )
            )

        if ids:
            logger.info(
                "Found %d unprocessed requests from previous run",
                len(ids),
            )

        for request_id in ids:
            await self.process_request(request_id)
