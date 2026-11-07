from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    ollama_base_url: str
    ollama_model: str
    log_level: str


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задан {name} в .env")
    return value


def load_config() -> Config:
    level = required("LOG_LEVEL").upper()

    if level not in {
        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    }:
        raise RuntimeError(f"Некорректный LOG_LEVEL: {level}")

    return Config(
        bot_token=required("BOT_TOKEN"),
        db_host=required("DB_HOST"),
        db_port=int(required("DB_PORT")),
        db_name=required("POSTGRES_DB"),
        db_user=required("POSTGRES_USER"),
        db_password=required("POSTGRES_PASSWORD"),
        ollama_base_url=required("OLLAMA_BASE_URL").rstrip("/"),
        ollama_model=required("OLLAMA_MODEL"),
        log_level=level,
    )
