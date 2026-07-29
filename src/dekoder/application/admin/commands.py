"""Команды Admin (docs/versions/05, §4) — единственный кросс-модульный оркестратор наравне с ai_core."""

from __future__ import annotations

from dataclasses import dataclass

from dekoder.shared.domain.identifiers import CaseId, DocumentId


@dataclass(frozen=True)
class AuthenticateAdminCommand:
    login: str
    password: str


@dataclass(frozen=True)
class UploadKnowledgeDocumentCommand:
    title: str
    category: str | None
    tags: tuple[str, ...]
    content: bytes


@dataclass(frozen=True)
class UpdateKnowledgeDocumentCommand:
    document_id: DocumentId
    title: str | None
    category: str | None
    tags: tuple[str, ...] | None


@dataclass(frozen=True)
class RemoveKnowledgeDocumentCommand:
    document_id: DocumentId


@dataclass(frozen=True)
class CreateKnowledgeCaseCommand:
    title: str
    input_data: str
    task_type: str
    expected_approach: str
    example_result: str


@dataclass(frozen=True)
class UpdateKnowledgeCaseCommand:
    case_id: CaseId
    title: str | None = None
    input_data: str | None = None
    task_type: str | None = None
    expected_approach: str | None = None
    example_result: str | None = None


@dataclass(frozen=True)
class ArchiveKnowledgeCaseCommand:
    case_id: CaseId


@dataclass(frozen=True)
class LinkDocumentToCaseCommand:
    document_id: DocumentId
    case_id: CaseId
