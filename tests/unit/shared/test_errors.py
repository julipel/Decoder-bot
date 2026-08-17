"""Тесты базовой иерархии ошибок (shared/errors.py)."""

from __future__ import annotations

import pytest

from dekoder.shared.errors import (
    ApplicationError,
    DekoderError,
    ExternalServiceError,
    InfrastructureError,
    LLMProviderError,
    ValidationError,
)


class TestHierarchy:
    @pytest.mark.parametrize(
        "error_cls",
        [ValidationError, ApplicationError, InfrastructureError, ExternalServiceError, LLMProviderError],
    )
    def test_all_errors_are_dekoder_errors(self, error_cls: type[DekoderError]) -> None:
        assert issubclass(error_cls, DekoderError)

    def test_external_service_error_is_infrastructure_error(self) -> None:
        assert issubclass(ExternalServiceError, InfrastructureError)

    def test_llm_provider_error_is_external_service_error(self) -> None:
        assert issubclass(LLMProviderError, ExternalServiceError)
        assert issubclass(LLMProviderError, InfrastructureError)

    def test_validation_and_application_errors_are_not_infrastructure_errors(self) -> None:
        assert not issubclass(ValidationError, InfrastructureError)
        assert not issubclass(ApplicationError, InfrastructureError)


class TestRequiredFields:
    def test_message_and_user_message_are_stored(self) -> None:
        error = ApplicationError("db row missing pk", "Что-то пошло не так.")

        assert error.message == "db row missing pk"
        assert error.user_message == "Что-то пошло не так."
        assert str(error) == "db row missing pk"

    @pytest.mark.parametrize(
        ("error_cls", "expected_code"),
        [
            (ValidationError, "VALIDATION_ERROR"),
            (ApplicationError, "APPLICATION_ERROR"),
            (InfrastructureError, "INFRASTRUCTURE_ERROR"),
            (ExternalServiceError, "EXTERNAL_SERVICE_ERROR"),
            (LLMProviderError, "LLM_PROVIDER_ERROR"),
        ],
    )
    def test_default_code_matches_class(self, error_cls: type[DekoderError], expected_code: str) -> None:
        error = error_cls("technical", "user-safe")

        assert error.code == expected_code

    def test_code_can_be_overridden_explicitly(self) -> None:
        error = LLMProviderError("timeout calling provider", "Модель недоступна.", code="LLM_TIMEOUT")

        assert error.code == "LLM_TIMEOUT"


class TestRepr:
    def test_repr_includes_code_and_message(self) -> None:
        error = ValidationError("field required", "Проверьте введённые данные.")

        assert repr(error) == "ValidationError(code='VALIDATION_ERROR', message='field required')"


class TestOptionalFields:
    def test_cause_and_metadata_default_to_empty(self) -> None:
        error = ApplicationError("technical", "user-safe")

        assert error.cause is None
        assert error.metadata == {}

    def test_cause_is_stored_and_chained_as_dunder_cause(self) -> None:
        original = ValueError("root cause")

        error = InfrastructureError("wrapped failure", "Сервис недоступен.", cause=original)

        assert error.cause is original
        assert error.__cause__ is original

    def test_metadata_is_stored(self) -> None:
        error = LLMProviderError(
            "provider returned 503",
            "Модель временно недоступна, попробуйте позже.",
            metadata={"provider": "test-provider", "correlation_id": "corr-1"},
        )

        assert error.metadata == {"provider": "test-provider", "correlation_id": "corr-1"}

    def test_metadata_default_is_not_shared_between_instances(self) -> None:
        first = ApplicationError("a", "a")
        second = ApplicationError("b", "b")

        first.metadata["leaked"] = True

        assert "leaked" not in second.metadata


class TestSafeUserMessageIsIndependentOfTechnicalMessage:
    def test_user_message_does_not_have_to_match_technical_message(self) -> None:
        error = LLMProviderError(
            message="LLM provider API key sk-real-secret-value rejected with 401",
            user_message="Не удалось получить ответ модели. Попробуйте позже.",
        )

        assert "sk-real-secret-value" not in error.user_message
