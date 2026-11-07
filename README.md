# ITMO · Лабораторная №7 — прототип ИИ-автоматизации

**Telegram → aiogram 3 → PostgreSQL (`requests`) → Ollama / Qwen3 → Pydantic → PostgreSQL (`analyses`) → логи.**

Учебный прототип автоматически обрабатывает текстовые обращения студентов. Новое сообщение в **личном чате Telegram-бота** служит триггером: приложение сохраняет исходный текст в PostgreSQL, отправляет его в локальную LLM через Ollama HTTP API, проверяет JSON-ответ по схеме Pydantic и записывает результат анализа в базу.

**Важно:** бот отвечает на `/start`, но **не отправляет пользователю результаты анализа**. Они доступны в PostgreSQL и логах.

## Как устроен проект

```text
Telegram (личное текстовое сообщение)
                │
                ▼
      Python / aiogram 3
                │
                ▼
  PostgreSQL: requests (new → processing)
                │
                ▼
   Ollama HTTP API → Qwen3 4B Instruct
                │       + Modelfile
                ▼
     Pydantic: проверка JSON
                │
                ▼
   PostgreSQL: analyses (category, summary,
   requires_review, review_reason, raw_response)
                │
                ▼
     requests.status = processed / failed
                │
                ▼
        логи приложения / SQL
```

- `requests` хранит текст, технические идентификаторы Telegram и статус обработки. Пара `(telegram_chat_id, telegram_message_id)` защищает от повторного сохранения **одного и того же сообщения**.
- `analyses` хранит выбранную моделью категорию, краткое содержание, признак необходимости проверки человеком, объяснение, время обработки и **исходный JSON** в `raw_response`.
- Категории: `Учебные материалы`, `Расписание`, `Техническая проблема`, `Другое`.
- При ошибке обработки исходное обращение остаётся в `requests` со статусом `failed` и описанием в `error_message`.

`Modelfile` — **системная инструкция и параметры генерации для Ollama**, приложенные для воспроизводимости. Это не дообучение весов Qwen3 и не файл, который бот читает при каждом запросе. Из него однократно создают модель `lab7-student-assistant:latest` командой `ollama create`. Если такая модель на вашем компьютере уже создана, повторять этот шаг не нужно.

## Требования

- Docker Desktop / Docker Engine с Docker Compose V2;
- Telegram-бот и токен из [@BotFather](https://t.me/BotFather), интернет для Telegram Bot API;
- Ollama с моделью `lab7-student-assistant:latest` — на том же компьютере или на другом доступном узле;
- для **локального запуска бота** и тестов — Python 3.12+;
- сетевой доступ от процесса бота к Ollama API (на одном компьютере или через доверенную локальную сеть).

> **Один активный polling-процесс на один токен Telegram.** Не запускайте одновременно бота в Docker и через `python main.py`.

## 1. Подготовка Ollama

Установите [Ollama](https://ollama.com/) и выполните:

```bash
ollama pull qwen3:4b-instruct
ollama create lab7-student-assistant -f Modelfile
ollama list
```

`Modelfile` содержит нашу инструкцию для модели и настройки генерации. Это не обучение модели, а её конфигурация. При желании можно заменить базовую модель в строке `FROM` и создать свою версию.

## 2. Настройка `.env`

Создайте файл из шаблона:

```bash
cp .env.example .env
```

Заполните значения в `.env`:

```dotenv
BOT_TOKEN=YOUR_BOT_TOKEN

DB_HOST=127.0.0.1
DB_PORT=5434
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_PASSWORD

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=lab7-student-assistant:latest
LOG_LEVEL=INFO
```

Токен можно получить через [@BotFather](https://t.me/BotFather). Адрес Ollama зависит от запуска:

- **Бот в Docker, Ollama на том же компьютере:** `http://host.docker.internal:11434` (Docker Desktop).
- **Бот и Ollama запущены локально:** `http://127.0.0.1:11434`.
- **Ollama на другом компьютере:** `http://IP_OLLAMA:11434`.

Ollama должна принимать соединения по выбранному адресу: при доступе из Docker или по сети может потребоваться настройка `OLLAMA_HOST` и firewall.

## 3. Основной запуск — Docker Compose

PostgreSQL и бот запускаются вместе; Ollama должна быть запущена отдельно.

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

Отправьте боту `/start`, затем обычное текстовое обращение. Результат сохранится в PostgreSQL.

Остановить контейнеры без удаления данных:

```bash
docker compose down
```

## 4. Альтернатива — бот локально, база в Docker

```bash
docker compose stop bot  # чтобы не работали два экземпляра одного бота
docker compose up -d db  # только PostgreSQL
python3 -m venv .venv
source .venv/bin/activate  # bash/zsh; для fish: source .venv/bin/activate.fish
python -m pip install -r requirements.txt
python main.py
```

Локальный бот использует `DB_HOST=127.0.0.1` и `DB_PORT=5434` из `.env`; контейнерный — `db:5432` из `compose.yaml`. Если Ollama тоже локальная, укажите `OLLAMA_BASE_URL=http://127.0.0.1:11434`.

Чтобы вернуться к Docker: остановите Python через `Ctrl+C`, затем выполните `docker compose up -d bot`.

## 5. База и тесты

Подключение к PostgreSQL из DataGrip: **`127.0.0.1:5434`**, имя БД, пользователь и пароль — из `.env`. Таблицы `requests` и `analyses` создаются при запуске приложения. Исходный JSON модели хранится в `analyses.raw_response`.

Тесты запускаются отдельно:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -v
```
Они проверяют JSON-контракт и HTTP-запросы через `httpx.MockTransport`, **не добавляя тестовые обращения в базу**.

## Обратная связь

Если возникли вопросы или проблемы с развертыванием проекта, настройкой Docker Compose или Ollama, можете написать мне в Telegram: [@voronkov44](https://t.me/voronkov44).