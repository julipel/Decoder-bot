"""
ProcessUserMessage — основной use case первого вертикального среза
(Telegram → ProcessUserMessage → LLMProvider → OpenRouter → ответ).

Зависит только от порта `LLMProvider`, DTO собственного модуля и
доменного `MessageText` — ни httpx, ни Telegram, ни FastAPI, ни URL
конкретного провайдера, ни переменных окружения, ни сохранения данных.
Настройки (`default_model`/`system_prompt`/`temperature`/`max_tokens`)
приходят через конструктор — это ответственность bootstrap-слоя.

`User`/`Conversation`/`Memory`/`Prompt Engine`/`RAG` сюда не входят —
следующие этапы.
"""

from __future__ import annotations

from dekoder.application.conversation.dto import (
    LLMRequest,
    ProcessUserMessageCommand,
    ProcessUserMessageResult,
    TokenUsage,
)
from dekoder.application.conversation.ports import LLMProvider
from dekoder.domain.conversation.value_objects import MessageText, ModelId
from dekoder.shared.errors import ValidationError


class ProcessUserMessage:
    def __init__(
        self,
        llm_provider: LLMProvider,
        default_model: ModelId,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._llm_provider = llm_provider
        self._default_model = default_model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def execute(self, command: ProcessUserMessageCommand) -> ProcessUserMessageResult:
        message_text = self._validate_message_text(command.message_text)
        model_id = command.model_id if command.model_id is not None else self._default_model

        request = LLMRequest(
            system_prompt=self._system_prompt,
            user_message=message_text,
            model_id=model_id,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            correlation_id=command.correlation_id,
        )
        response = await self._llm_provider.generate(request)

        return ProcessUserMessageResult(
            response_text=response.text,
            provider_id=response.provider_id,
            model_id=response.model_id,
            duration_ms=response.duration_ms,
            usage=TokenUsage(input_tokens=response.input_tokens, output_tokens=response.output_tokens),
        )

    @staticmethod
    def _validate_message_text(raw_text: str) -> MessageText:
        try:
            return MessageText(raw_text)
        except ValueError as error:
            raise ValidationError(
                message=f"Некорректный текст пользовательского сообщения: {error}",
                user_message="Сообщение не может быть пустым.",
                cause=error,
            ) from error
