"""Тесты структурированного логирования (shared/logging.py)."""

from __future__ import annotations

import json

import pytest

from dekoder.shared.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def _reset_context() -> None:
    """Гарантирует, что contextvars не утекают между тестами."""
    clear_request_context()
    yield
    clear_request_context()


def _read_last_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out = capsys.readouterr().out.strip().splitlines()
    assert out, "ожидалась хотя бы одна строка журнала"
    return json.loads(out[-1])


class TestLoggerCreatedBeforeConfiguration:
    def test_module_level_logger_still_renders_json_after_late_configure(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """
        Регрессия, найденная при ручной проверке в Docker: `get_logger()`
        раньше вызывал `.bind()` немедленно, из-за чего логгер, созданный
        на уровне модуля (обычный паттерн `_logger = get_logger(__name__)`
        — при импорте, до `configure_logging()` в bootstrap-слое),
        навсегда застревал на дефолтной консольной конфигурации
        structlog вместо JSON, даже после успешного `configure_logging()`.
        """
        early_logger = get_logger("dekoder.early")

        configure_logging(environment="test")
        early_logger.info("event_after_late_configure")

        entry = _read_last_log_line(capsys)

        assert entry["event"] == "event_after_late_configure"
        assert entry["logger"] == "dekoder.early"
        assert entry["environment"] == "test"


class TestRequiredFields:
    def test_log_entry_contains_required_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        get_logger("dekoder.test").info("something_happened")

        entry = _read_last_log_line(capsys)

        assert entry["event"] == "something_happened"
        assert entry["logger"] == "dekoder.test"
        assert entry["level"] == "info"
        assert entry["environment"] == "test"
        assert "timestamp" in entry

    def test_environment_reflects_configured_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="production")
        get_logger("dekoder.test").info("event_x")

        entry = _read_last_log_line(capsys)

        assert entry["environment"] == "production"


class TestOptionalRequestFields:
    def test_bound_request_fields_appear_in_log_entry(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        bind_request_context(correlation_id="corr-123", provider="openrouter", model="gpt-4o-mini", duration=1.23)
        get_logger("dekoder.test").info("model_call_completed")

        entry = _read_last_log_line(capsys)

        assert entry["correlation_id"] == "corr-123"
        assert entry["provider"] == "openrouter"
        assert entry["model"] == "gpt-4o-mini"
        assert entry["duration"] == 1.23

    def test_clear_request_context_removes_bound_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        bind_request_context(correlation_id="corr-123")
        clear_request_context()
        get_logger("dekoder.test").info("event_after_clear")

        entry = _read_last_log_line(capsys)

        assert "correlation_id" not in entry

    def test_unset_optional_fields_are_not_bound(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        bind_request_context(correlation_id="corr-only")
        get_logger("dekoder.test").info("partial_context")

        entry = _read_last_log_line(capsys)

        assert entry["correlation_id"] == "corr-only"
        assert "provider" not in entry
        assert "model" not in entry
        assert "duration" not in entry


class TestSensitiveFieldsAreRedacted:
    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("api_key", "sk-real-secret-value"),
            ("openrouter_api_key", "sk-real-secret-value"),
            ("bot_token", "123456:real-telegram-token"),
            ("telegram_bot_token", "123456:real-telegram-token"),
            ("authorization", "Bearer real-token-value"),
            ("message", "полный текст пользовательского сообщения"),
            ("response", "полный текст ответа модели"),
            ("password", "hunter2"),
        ],
    )
    def test_sensitive_key_is_redacted(self, capsys: pytest.CaptureFixture[str], key: str, value: str) -> None:
        configure_logging(environment="test")
        get_logger("dekoder.test").info("event_with_secret", **{key: value})

        entry = _read_last_log_line(capsys)

        assert entry[key] != value
        assert value not in json.dumps(entry)

    def test_non_sensitive_fields_pass_through_unredacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_logging(environment="test")
        get_logger("dekoder.test").info("event_x", status="ok", count=3)

        entry = _read_last_log_line(capsys)

        assert entry["status"] == "ok"
        assert entry["count"] == 3
