from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    category: Literal[
        "Учебные материалы",
        "Расписание",
        "Техническая проблема",
        "Другое",
    ]
    summary: str = Field(min_length=5, max_length=700)
    requires_review: bool
    review_reason: str = Field(max_length=700)


class OllamaClient:
    def __init__(self, *, base_url: str, model: str):
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
            trust_env=False,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def check_ready(self) -> None:
        response = await self.client.get("/api/tags")
        response.raise_for_status()

        models = response.json().get("models", [])
        names = (
            {item.get("name") for item in models}
            | {item.get("model") for item in models}
        )

        if self.model not in names:
            raise RuntimeError(
                f"Модель {self.model!r} не найдена в Ollama"
            )

    async def analyze(
        self,
        question: str,
    ) -> tuple[AnalysisResult, str]:

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "context": None,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            "format": AnalysisResult.model_json_schema(),
        }

        response = await self.client.post(
            "/api/chat",
            json=payload,
        )
        response.raise_for_status()

        content = response.json()["message"]["content"]
        result = AnalysisResult.model_validate_json(content)

        return result, content
