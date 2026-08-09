"""
Сценарий 5 «Плана реализации.md» (§18.4, RAG) — Sprint 10, задача S10-02,
ADR-10.2. Единственный из семи обязательных сценариев, ранее structurally
непроверяемый e2e-тестом: `FakeAsyncQdrantClient.query_points()` до этой
задачи безусловно возвращал `points=[]` (докстринг `tests/support/
fake_qdrant_client.py`) — теперь выполняет реальный косинусный поиск.

Один непрерывный сценарий (по образцу `tests/e2e/test_admin_scenario.py`):
администратор загружает релевантный и (для контраста) нерелевантный
документ через admin REST реального `create_application(settings)`
приложения → документ реально проходит `TxtParser`/`StructuralChunker`/
`OpenAiEmbeddingProvider` (respx-мок только на HTTP-границе) →
индексируется в `FakeAsyncQdrantClient` → пользователь задаёт вопрос через
реальный `ProcessUserMessage`/Telegram-хендлер ТОГО ЖЕ приложения
(`app.state.container.process_user_message`, собранный тем же lifespan) →
находится и используется в промпте правильный фрагмент.

Admin-путь и Telegram-путь работают в одном и том же asyncio event loop
(`app.router.lifespan_context(app)` + `httpx.AsyncClient(transport=
ASGITransport(app=app))`, не `starlette.testclient.TestClient`, который
поднимает отдельный поток/loop) — так `app.state.container.
process_user_message` (собранный внутри lifespan) можно безопасно вызвать
напрямую из того же теста без риска смешать `aiosqlite`-соединения между
разными event loop'ами. `fake_qdrant_client` — один и тот же объект,
подставленный в lifespan через monkeypatch `bootstrap.application.
build_qdrant_client` (не через `app.dependency_overrides`, которые влияют
только на FastAPI `Depends()`, но не на клиент, который lifespan сам
передаёт в `build_container()` для `ProcessUserMessage.knowledge_search`)
— поэтому admin-загрузка и поиск пользователя видят одни и те же точки.

Детерминированный bag-of-words эмбеддинг-мок (`_bag_of_words_embedding`) —
фиксированный словарь ключевых слов, не настоящая семантика (ADR-10.2,
«Недостатки»): достаточно, чтобы подтвердить, что конвейер технически
находит и передаёт правильный контекст, реальное качество ранжирования
вне скоупа тестирования MVP.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
import respx
from telegram import Update
from telegram.ext import Application, MessageHandler
from tests.support.fake_qdrant_client import FakeAsyncQdrantClient

from dekoder.bootstrap import application as bootstrap_application
from dekoder.bootstrap.application import create_application
from dekoder.infrastructure.persistence.base import Base
from dekoder.infrastructure.persistence.engine import create_database_engine
from dekoder.infrastructure.persistence.profile_orm import ProfileORM
from dekoder.infrastructure.persistence.session import create_session_factory
from dekoder.presentation.telegram.bot import build_telegram_application, register_message_handler
from dekoder.shared.config import Settings
from dekoder.shared.logging import clear_request_context, configure_logging

_ADMIN_KEY_HEADER = {"X-Admin-Api-Key": "e2e-admin-api-key"}
_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
_TEST_BOT_TOKEN = "123456:test-token"  # noqa: S105 - фиктивный токен для теста, не секрет

# Детерминированный bag-of-words словарь (ADR-10.2): документ о гарантии и
# вопрос по нему делят первые четыре слова, документ-рецепт (нерелевантный
# контраст) — последние четыре, пересечения между группами нет.
_VOCABULARY = ["гарантия", "месяца", "смартфон", "x500", "борщ", "картофель", "рецепт", "капуста"]
_TOKEN_PATTERN = re.compile(r"[a-zа-яё0-9]+")

_RELEVANT_DOCUMENT_TEXT = (
    "Гарантия на смартфон x500 действует 24 месяца. Гарантия распространяется на заводские дефекты смартфон."
)
_IRRELEVANT_DOCUMENT_TEXT = "Рецепт: борщ борщ картофель капуста. Простой рецепт борщ на кухне."
_RELEVANT_QUESTION = "Сколько месяца действует гарантия на смартфон x500?"
_UNRELATED_QUESTION = "Какая завтра погода в городе?"
_LLM_REPLY_TEXT = "Гарантия на смартфон X500 действует 24 месяца."


def _bag_of_words_embedding(text: str) -> list[float]:
    """Считает вектор как количество вхождений слов фиксированного словаря — без реального ML (ADR-10.2)."""
    tokens = _TOKEN_PATTERN.findall(text.lower())
    counts = Counter(tokens)
    return [float(counts.get(word, 0)) for word in _VOCABULARY]


def _profile_orm(*, name: str = "Дефолт", is_default: bool = True) -> ProfileORM:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)
    return ProfileORM(
        id=uuid4(),
        name=name,
        description="Описание",
        system_instruction="Инструкция",
        response_style="нейтральный",
        target_audience="все",
        formality_level="нейтральный",
        preferred_structure="без требований",
        forbidden_phrasing=[],
        preferred_model=None,
        response_length_hint=None,
        additional_constraints="",
        status="active",
        is_system=True,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "e2e-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "e2e-webhook-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "e2e-openrouter-key")
    monkeypatch.setenv("OPENAI_API_KEY", "e2e-openai-key")
    monkeypatch.setenv("ADMIN_API_KEY", "e2e-admin-api-key")
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'e2e-rag.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("KNOWLEDGE_STORAGE_PATH", str(tmp_path / "knowledge_documents"))

    schema_engine = create_database_engine(database_url)
    async with schema_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(schema_engine)
    async with session_factory() as session:
        session.add(_profile_orm())
        await session.commit()
    await schema_engine.dispose()

    return Settings()


@pytest.fixture
def fake_qdrant_client() -> FakeAsyncQdrantClient:
    return FakeAsyncQdrantClient()


@pytest.fixture
def app_with_shared_fake_qdrant(
    settings: Settings, fake_qdrant_client: FakeAsyncQdrantClient, monkeypatch: pytest.MonkeyPatch
) -> Any:
    """
    Один и тот же `fake_qdrant_client` подставляется в lifespan через
    monkeypatch `build_qdrant_client` (не `app.dependency_overrides`, см.
    докстринг модуля) — и admin-документный конвейер, и `ProcessUserMessage.
    knowledge_search` внутри `app.state.container` получают ОДИН и тот же
    объект (ADR-10.2, checklist: «не два раздельных приложения/дублёра»).
    """
    monkeypatch.setattr(bootstrap_application, "build_qdrant_client", lambda _settings: fake_qdrant_client)
    return create_application(settings)


def _mock_embeddings_route() -> None:
    def _respond(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": _bag_of_words_embedding(t)} for i, t in enumerate(texts)]}
        )

    respx.post(_EMBEDDINGS_URL).mock(side_effect=_respond)


def _mock_llm_route(captured_requests: list[dict[str, Any]], reply_text: str) -> None:
    def _respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        captured_requests.append(payload)
        return httpx.Response(
            200,
            json={
                "id": "gen-1",
                "model": payload["model"],
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": reply_text}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    respx.post(_CHAT_COMPLETIONS_URL).mock(side_effect=_respond)


def _text_handler_callback(application: Application) -> Any:
    """Достаёт callback уже зарегистрированного `MessageHandler` (текстовые сообщения) — по образцу `_handler_callbacks`
    в `tests/e2e/test_conversation_persistence_scenario.py` (без обращения к сети/`Application.initialize()`)."""
    for handler in application.handlers[0]:
        if isinstance(handler, MessageHandler):
            return handler.callback
    raise AssertionError("MessageHandler не зарегистрирован")


def _make_update(text: str, user_id: int) -> MagicMock:
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(id=user_id)
    update.effective_message = MagicMock()
    update.effective_message.text = text
    update.effective_message.reply_text = AsyncMock()
    return update


def _admin_http_client(app: Any) -> httpx.AsyncClient:
    """`httpx.AsyncClient` поверх `ASGITransport` — вызывает `app` напрямую в текущем event loop,
    не через `starlette.testclient.TestClient` (отдельный поток) — см. докстринг модуля."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def _upload_document(admin_client: httpx.AsyncClient, *, filename: str, title: str, content: str) -> str:
    response = await admin_client.post(
        "/admin/documents",
        headers=_ADMIN_KEY_HEADER,
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        data={"title": title},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["status"] == "indexed"
    document_id: str = document["id"]
    return document_id


class TestRagScenario:
    """Сценарий 5 (§18.4): загрузка → индексация → вопрос → найденный контекст → ответ на его основе."""

    @respx.mock
    async def test_relevant_document_found_and_used_in_prompt_not_irrelevant_one(
        self, app_with_shared_fake_qdrant: Any
    ) -> None:
        app = app_with_shared_fake_qdrant
        _mock_embeddings_route()
        captured_llm_requests: list[dict[str, Any]] = []
        _mock_llm_route(captured_llm_requests, _LLM_REPLY_TEXT)

        async with app.router.lifespan_context(app):
            async with _admin_http_client(app) as admin_client:
                relevant_document_id = await _upload_document(
                    admin_client,
                    filename="warranty.txt",
                    title="Гарантия на смартфон X500",
                    content=_RELEVANT_DOCUMENT_TEXT,
                )
                irrelevant_document_id = await _upload_document(
                    admin_client,
                    filename="recipe.txt",
                    title="Рецепт борща",
                    content=_IRRELEVANT_DOCUMENT_TEXT,
                )
            assert relevant_document_id != irrelevant_document_id

            process_user_message = app.state.container.process_user_message
            telegram_application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
            register_message_handler(telegram_application, process_user_message)
            text_handler = _text_handler_callback(telegram_application)

            update = _make_update(_RELEVANT_QUESTION, user_id=101)
            await text_handler(update, MagicMock())

        # --- AC-2: промпт, отправленный LLM, содержит текст найденного фрагмента ---
        assert len(captured_llm_requests) == 1
        sent_messages = captured_llm_requests[0]["messages"]
        system_prompt = next(m["content"] for m in sent_messages if m["role"] == "system")
        assert _RELEVANT_DOCUMENT_TEXT in system_prompt
        assert _IRRELEVANT_DOCUMENT_TEXT not in system_prompt

        # --- ответ пользователю построен на основе найденного контекста ---
        update.effective_message.reply_text.assert_awaited_once_with(_LLM_REPLY_TEXT)

    @respx.mock
    async def test_unrelated_question_yields_zero_chunks_and_reply_is_still_generated(
        self, app_with_shared_fake_qdrant: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:
        app = app_with_shared_fake_qdrant
        _mock_embeddings_route()
        captured_llm_requests: list[dict[str, Any]] = []
        _mock_llm_route(captured_llm_requests, "Не нашёл информации по вашему вопросу.")

        clear_request_context()
        configure_logging(environment="test")

        async with app.router.lifespan_context(app):
            async with _admin_http_client(app) as admin_client:
                await _upload_document(
                    admin_client,
                    filename="warranty.txt",
                    title="Гарантия на смартфон X500",
                    content=_RELEVANT_DOCUMENT_TEXT,
                )

            process_user_message = app.state.container.process_user_message
            telegram_application = build_telegram_application(bot_token=_TEST_BOT_TOKEN)
            register_message_handler(telegram_application, process_user_message)
            text_handler = _text_handler_callback(telegram_application)

            update = _make_update(_UNRELATED_QUESTION, user_id=102)
            await text_handler(update, MagicMock())

        # --- AC-3: knowledge_search_completed с chunks_found=0, ответ всё равно сгенерирован ---
        log_lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines() if line.strip()]
        search_events = [line for line in log_lines if line.get("event") == "knowledge_search_completed"]
        assert len(search_events) == 1
        assert search_events[0]["chunks_found"] == 0

        assert len(captured_llm_requests) == 1
        update.effective_message.reply_text.assert_awaited_once_with("Не нашёл информации по вашему вопросу.")
        clear_request_context()
