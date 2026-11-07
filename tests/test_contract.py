import json

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.ollama import AnalysisResult, OllamaClient


def test_valid_response():
    result = AnalysisResult.model_validate({
        "category": "Учебные материалы",
        "summary": "Студент не может найти задание по лабораторной работе.",
        "requires_review": True,
        "review_reason": "Нет информации о месте публикации задания.",
    })
    assert result.requires_review is True


@pytest.mark.parametrize("patch", [
    {"category": "Финансы"},
    {"requires_review": "true"},
    {"summary": ""},
    {"extra": "выдумано"},
])
def test_invalid_schema(patch):
    valid = {
        "category": "Другое",
        "summary": "Тестовое обращение студента",
        "requires_review": True,
        "review_reason": "Недостаточно сведений",
    }
    valid.update(patch)

    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(valid)


@pytest.mark.asyncio
async def test_ollama_request_uses_only_user_message_and_schema():
    seen = {}

    def responder(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        seen.update(data)

        return httpx.Response(200, json={
            "message": {
                "content": json.dumps({
                    "category": "Другое",
                    "summary": "Студент направил тестовое обращение",
                    "requires_review": True,
                    "review_reason": "Не указан контекст",
                }, ensure_ascii=False)
            }
        })

    client = OllamaClient(
        base_url="http://example.test",
        model="lab7-student-assistant:latest",
    )

    await client.client.aclose()
    client.client = httpx.AsyncClient(
        base_url="http://example.test",
        transport=httpx.MockTransport(responder),
    )

    try:
        result, raw = await client.analyze("Что задано?")

        # Проверяем, что json модели совпадает с результатом pydantic
        assert json.loads(raw) == result.model_dump()

        assert result.category == "Другое"
        assert len(seen["messages"]) == 1
        assert seen["messages"][0]["role"] == "user"
        assert json.loads(
            seen["messages"][0]["content"]
        )["question"] == "Что задано?"
        assert seen["format"]["type"] == "object"
        assert seen["stream"] is False

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ollama_check_ready():
    def responder(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "models": [
                {"name": "lab7-student-assistant:latest"}
            ]
        })

    client = OllamaClient(
        base_url="http://example.test",
        model="lab7-student-assistant:latest",
    )

    await client.client.aclose()
    client.client = httpx.AsyncClient(
        base_url="http://example.test",
        transport=httpx.MockTransport(responder),
    )

    try:
        await client.check_ready()
    finally:
        await client.close()
