"""
`admin_documents_router` — защищённый REST-доступ к CRUD документов базы
знаний (Sprint 8, задача S8-05, ADR-8.4/8.6).

Все пять эндпоинтов защищены `require_admin_api_key` на уровне
`APIRouter` (не полагаясь на порядок подключения в `create_application()`
— защита «в глубину», ADR-8.2). `POST /admin/documents` — синхронный
HTTP-запрос, ждущий завершения всего 12-шагового конвейера индексации
(явно принятое MVP-ограничение, ADR-8.6, «Недостатки»: очередь/фоновые
задачи вне скоупа Sprint 8).

`DELETE` идемпотентен (204 даже для уже отсутствующего документа, тот
же прецедент, что `DeleteKnowledgeDocumentUseCase.execute()` и
`MessageRepository.clear`) — `GET {id}`/`reindex` для несуществующего
документа поднимают `NotFoundError`/404 (это операции над конкретным
ресурсом, где «нет ресурса» — содержательная ошибка клиента).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import Response

from dekoder.application.knowledge.dto import IndexDocumentCommand
from dekoder.presentation.api.dependencies.auth import require_admin_api_key
from dekoder.presentation.api.dependencies.documents import DocumentUseCases, get_document_use_cases
from dekoder.presentation.api.schemas.documents import DocumentResponse
from dekoder.shared.errors import NotFoundError

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"], dependencies=[Depends(require_admin_api_key)])


def _parse_tags(raw_tags: str | None) -> tuple[str, ...]:
    if not raw_tags:
        return ()
    return tuple(tag.strip() for tag in raw_tags.split(",") if tag.strip())


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    title: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    description: str | None = Form(default=None),
    use_cases: DocumentUseCases = Depends(get_document_use_cases),
) -> DocumentResponse:
    content = await file.read()
    source_filename = file.filename or "unnamed"
    command = IndexDocumentCommand(
        title=title or source_filename,
        source_filename=source_filename,
        content=content,
        tags=_parse_tags(tags),
        description=description,
    )
    result = await use_cases.index.execute(command)
    return DocumentResponse.model_validate(result.document)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(use_cases: DocumentUseCases = Depends(get_document_use_cases)) -> list[DocumentResponse]:
    documents = await use_cases.list_all.execute()
    return [DocumentResponse.model_validate(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID, use_cases: DocumentUseCases = Depends(get_document_use_cases)
) -> DocumentResponse:
    document = await use_cases.get.execute(document_id)
    if document is None:
        raise NotFoundError(
            message=f"Документ {document_id} не найден",
            user_message="Документ не найден.",
        )
    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: UUID, use_cases: DocumentUseCases = Depends(get_document_use_cases)) -> Response:
    await use_cases.delete.execute(document_id)
    return Response(status_code=204)


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    document_id: UUID, use_cases: DocumentUseCases = Depends(get_document_use_cases)
) -> DocumentResponse:
    result = await use_cases.reindex.execute(document_id)
    if result is None:
        raise NotFoundError(
            message=f"Документ {document_id} не найден",
            user_message="Документ не найден.",
        )
    return DocumentResponse.model_validate(result.document)
