# Внутренние интерфейсы — MVP персонального AI-ассистента «Декодер»

**Версия:** 1.0
**Статус:** Approved
**Этап:** Проектирование архитектуры

**Связанные документы:**
- [`docs/01_requirements_analysis.md`](01_requirements_analysis.md)
- [`docs/02_system_architecture.md`](02_system_architecture.md)
- [`docs/03_project_structure.md`](03_project_structure.md)
- [`docs/04_domain_model.md`](04_domain_model.md)

Документ описывает внутренние контракты системы: порты, репозитории, сервисы, ошибки, транзакционные границы и идемпотентность — чтобы последующая реализация не требовала новых архитектурных решений. Основан на утверждённых [`docs/01_requirements_analysis.md`](01_requirements_analysis.md), [`docs/02_system_architecture.md`](02_system_architecture.md), [`docs/03_project_structure.md`](03_project_structure.md), [`docs/04_domain_model.md`](04_domain_model.md) и на фактическом состоянии `src/dekoder/` (заглушках портов, use case'ов и адаптеров). Эти документы и код не изменялись.

Это **не** документ реализации: без SQL, без описания FastAPI/Telegram API, без физической схемы БД, без Python-сигнатур. Все контракты — в текстовом виде: назначение, параметры, возвращаемое значение, допустимые ошибки.

## Общая схема потока запроса

Упрощённая схема основного потока (детали — в разделах 5 и 10):

```
Telegram
   ↓
ConversationPort
   ↓
AI Core
   ↓
Profile · Memory · Search · LLM
   ↓
Logging
   ↓
Outgoing Response
```

## Документ не описывает

Ниже — то, что сознательно находится вне области действия этого документа (описано в других документах либо будет описано на следующих этапах):

- физическую схему базы данных;
- SQL;
- REST API;
- Telegram Bot API;
- реализацию адаптеров;
- конкретные классы инфраструктуры;
- конфигурацию окружения;
- детали реализации алгоритмов.

## 1. Порты по модулям (Inbound / Outbound)

Различение введено по одному правилу, применённому единообразно ко всем портам: **Inbound-порт** реализуется use case'ом того же модуля (это собственная бизнес-логика модуля, вызываемая извне); **Outbound-порт** реализуется инфраструктурным адаптером (SQLite/Qdrant/внешний провайдер) и используется use case'ами — своими или чужими — для доступа к данным/внешним системам. В MVP формальный Inbound-порт есть только там, где вызывающих реализаций действительно несколько или это явно предусмотрено докс/02 (Telegram → AI Core, а в будущем — другие каналы); там, где вызывающий всегда один и тот же (HTTP-панель → её собственные use case'ы), порт не вводится — это не пробел, а осознанная экономия абстракции, уже заложенная в docs/03.

### 1.1 AI Core

**Inbound:** `ConversationPort`
- Назначение: единственная точка входа в бизнес-логику ассистента для любого канала.
- Кто вызывает: `telegram/adapters/handlers.py` (`TelegramUpdateHandler`); в будущем — любой новый канал (docs/02, §12).
- Кто реализует: `ProcessUserMessageUseCase` (ai_core — use case, не адаптер).
- Жизненный цикл: реализация собирается один раз в composition root и живёт всё время работы процесса; вызывается на каждое входящее сообщение.
- Ответственность: принять `IncomingMessage`, вернуть `OutgoingResponse`; ничего не знает о Telegram или HTTP.

**Outbound, принадлежащих AI Core, нет.** AI Core не владеет ни одним портом — он собирает чужие: `ProfileRepositoryPort` (profile), `DialogueHistoryPort`/`FactRepositoryPort` (memory), `KnowledgeSearchPort` (search), `LLMPort` (llm), `LoggerPort` (logging_audit). Также напрямую (без порта, см. раздел 6) использует конкретные use case'ы memory: `StageFactUseCase`, `ConfirmFactUseCase`, `ListFactsUseCase`, `ForgetFactUseCase`.

### 1.2 Profile

**Inbound:** нет. `SeedProfileIfMissingUseCase` не вызывается через порт другим модулем — его вызывает composition root один раз при старте процесса (докс/03, `bootstrap.py`), это не межмодульное runtime-взаимодействие.

**Outbound:** `ProfileRepositoryPort`
- Назначение: получение и первичное сохранение единственного профиля автора.
- Кто вызывает: `BuildConversationContextUseCase` (ai_core, чтение); `SeedProfileIfMissingUseCase` (profile, чтение+запись при пустой БД).
- Кто реализует: `SqliteProfileRepository` (profile/adapters).
- Жизненный цикл: адаптер создаётся один раз в composition root (держит `SqliteConnectionFactory`), живёт всё время работы процесса.
- Ответственность: хранить ровно одну запись профиля; не содержит бизнес-правил (правило «профиль единственный» проверяет вызывающая сторона — seed use case).

### 1.3 Memory

**Inbound:** нет формального порта. Собственная бизнес-логика memory (`StageFactUseCase`, `ConfirmFactUseCase`, `ListFactsUseCase`, `ForgetFactUseCase`) вызывается напрямую как конкретные классы — это документированное исключение, см. раздел 6.

**Outbound:** `DialogueHistoryPort`
- Назначение: история диалога как последовательность отдельных реплик.
- Кто вызывает: `ProcessUserMessageUseCase` (запись), `BuildConversationContextUseCase` (чтение, `get_recent`).
- Кто реализует: `SqliteDialogueHistoryRepository` (memory/adapters).
- Жизненный цикл: как у `ProfileRepositoryPort` — создаётся один раз в composition root.
- Ответственность: только физическое хранение реплик; не решает, сколько реплик «достаточно» для контекста (размер окна передаёт вызывающая сторона параметром `limit`).

**Outbound:** `FactRepositoryPort`
- Назначение: черновики и подтверждённые факты пользователя одним портом (docs/02, §16.3 — намеренное решение, не два порта).
- Кто вызывает: `StageFactUseCase`, `ConfirmFactUseCase`, `ListFactsUseCase`, `ForgetFactUseCase` (memory, каждый — одна операция); `BuildConversationContextUseCase` (ai_core, `list_confirmed` — чтение).
- Кто реализует: `SqliteFactRepository` (memory/adapters) — один класс, обслуживающий и черновики, и факты.
- Жизненный цикл: как у остальных SQLite-репозиториев.
- Ответственность: хранение; проверка инварианта «не более одного активного черновика на пользователя» (docs/04, §1.3) — ответственность реализации порта, а не вызывающего use case'а, поскольку это правило о состоянии хранилища, а не о бизнес-процессе.

### 1.4 Knowledge Base

**Inbound:** нет — модуль вообще не имеет use case'ов (docs/03), только CRUD-порты.

**Outbound:** `DocumentRepositoryPort`
- Назначение: CRUD метаданных документа.
- Кто вызывает: `UploadDocumentUseCase`, `UpdateDocumentUseCase`, `RemoveDocumentUseCase`, `ListDocumentsUseCase` (admin); `IndexDocumentUseCase` (search — чтение метаданных/содержимого и запись `index_status`).
- Кто реализует: `SqliteDocumentRepository` (knowledge_base/adapters).
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: хранение метаданных; не решает, когда индексировать и не удаляет фрагменты/файл при `delete()` — это ответственность вызывающего use case'а (`RemoveDocumentUseCase`, раздел 8).

**Outbound:** `CaseRepositoryPort`
- Назначение: CRUD кейсов и связей «документ—кейс».
- Кто вызывает: `CreateCaseUseCase`, `UpdateCaseUseCase`, `ArchiveCaseUseCase`, `LinkDocumentToCaseUseCase`, `ListCasesUseCase` (admin); `IndexDocumentUseCase.index_case` (search — чтение).
- Кто реализует: `SqliteCaseRepository` (knowledge_base/adapters).
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: хранение кейсов и таблицы связей; не архивирует автоматически связанные фрагменты (docs/04, §1.6 — открытый вопрос).

**Outbound:** `FileStoragePort`
- Назначение: оригиналы файлов документов, отдельно от метаданных (docs/01, §4.6).
- Кто вызывает: `UploadDocumentUseCase` (запись), `RemoveDocumentUseCase` (удаление); `IndexDocumentUseCase` (чтение содержимого для разбиения на фрагменты).
- Кто реализует: `LocalFileStorageAdapter` (knowledge_base/adapters) — постоянный том (docs/02, §16.4).
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: только байты файла по `document_id`; не проверяет существование записи метаданных (эта согласованность — на вызывающей стороне).

### 1.5 Search

**Inbound:** `KnowledgeSearchPort`
- Назначение: семантический поиск фрагментов документов/кейсов.
- Кто вызывает: `BuildConversationContextUseCase` (ai_core).
- Кто реализует: `SearchFragmentsUseCase` (search — use case, не адаптер; use case сам является реализацией порта).
- Жизненный цикл: один экземпляр на процесс, держит `EmbeddingPort` и `VectorStorePort`.
- Ответственность: превратить текстовый запрос в вектор и найти ближайшие фрагменты; не решает, что делать при недоступности — это решает вызывающая сторона (`BuildConversationContextUseCase`, docs/02 §11).

**Inbound:** `IndexingPort`
- Назначение: индексация/переиндексация/удаление из индекса.
- Кто вызывает: use case'ы admin (`UploadDocumentUseCase`, `UpdateDocumentUseCase`, `RemoveDocumentUseCase`, `CreateCaseUseCase`, `UpdateCaseUseCase`, `LinkDocumentToCaseUseCase`).
- Кто реализует: `IndexDocumentUseCase` (search — use case).
- Жизненный цикл: один экземпляр на процесс, держит `DocumentRepositoryPort`/`CaseRepositoryPort`/`FileStoragePort` (knowledge_base), `DocumentChunker`, `EmbeddingPort`, `VectorStorePort`.
- Ответственность: единственное место, где search читает knowledge_base (docs/02, §6); не решает бизнес-правила admin (аудит, порядок операций) — их обеспечивает вызывающий use case admin.

**Outbound:** `EmbeddingPort`
- Назначение: векторное представление текста; конфигурируется независимо от `LLMPort` (docs/02, §16.2).
- Кто вызывает: `SearchFragmentsUseCase` (запрос), `IndexDocumentUseCase` (фрагменты документа/кейса).
- Кто реализует: `YandexGptEmbeddingAdapter` либо `OpenAiEmbeddingAdapter` (search/adapters) — ровно один активный, по `EMBEDDING_PROVIDER`.
- Жизненный цикл: выбирается в composition root при старте по конфигурации; не меняется во время работы процесса.
- Ответственность: только вычисление вектора; не имеет доступа к Qdrant.

**Outbound:** `VectorStorePort`
- Назначение: абстракция над векторным хранилищем, скрывает клиент Qdrant от use case'ов.
- Кто вызывает: `SearchFragmentsUseCase` (`query`), `IndexDocumentUseCase` (`upsert`, `delete_by_source`).
- Кто реализует: `QdrantVectorStore` (search/adapters).
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: только операции над векторным индексом; не знает про `Document`/`Case` как сущности — только про `source_type`/`source_id`.

### 1.6 LLM

**Inbound:** нет.

**Outbound:** `LLMPort`
- Назначение: генерация ответа активным поставщиком, независимо от AI Core.
- Кто вызывает: `GenerateAssistantResponseUseCase` (ai_core).
- Кто реализует: `YandexGptLLMAdapter` либо `OpenAiLLMAdapter` (llm/adapters) — ровно один активный, по `LLM_PROVIDER`.
- Жизненный цикл: выбирается в composition root по конфигурации при старте.
- Ответственность: вызов внешнего API и возврат текста + идентификатора поставщика/модели; не решает, что включать в промпт (это уже сделано вызывающей стороной в `LLMRequestContext`).

### 1.7 Admin

**Inbound:** нет — HTTP-роуты (`admin/adapters/http/routes.py`) вызывают use case'ы admin напрямую, конкретными классами (аналогично тому, как ai_core обращается к use case'ам memory, см. раздел 6); отдельный формальный порт не введён, так как у панели администратора нет и не предполагается других driving-адаптеров, кроме HTTP.

**Outbound:** `AdminAuthPort`
- Назначение: аутентификация единственной административной учётной записи.
- Кто вызывает: `AuthenticateAdminUseCase` (admin).
- Кто реализует: **адаптер не создан** в утверждённой структуре `docs/03` — там перечислены только `admin/adapters/http/routes.py` и `admin/adapters/http/session.py`, отдельного файла реализации `AdminAuthPort` (сравнение пароля с `ADMIN_PASSWORD_HASH`) нет. Это зафиксировано как открытый вопрос в «Замечаниях архитектора», а не решено самостоятельно.
- Жизненный цикл: (после появления адаптера) один экземпляр на процесс, читает `Settings.admin_login`/`admin_password_hash`.
- Ответственность: сравнение пароля с хешем, выдача/проверка токена сессии; не отвечает за механику cookie (это `AdminSessionCookies`, раздел 4).

### 1.8 Logging and Audit

**Inbound:** нет — используется как сквозной (cross-cutting) сервис.

**Outbound:** `LoggerPort`
- Назначение: технические журналы (stdout/stderr) и системные события, требующие анализа (docs/01, §4.8).
- Кто вызывает: любой модуль, у которого есть доступ к порту — в первую очередь `ProcessUserMessageUseCase`; также `TelegramUpdateHandler` (ошибки доставки).
- Кто реализует: `StdoutTechnicalLogger` (logging_audit/adapters).
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: `log_event` — только вывод в stdout/stderr; `log_system_error` — вывод в stdout/stderr **и** сохранение в SQLite через `SqliteSystemEventsRepository` (см. раздел 3 — контракт зафиксирован явно, поскольку в докс/01 §4.8 сказано, что такие ошибки «дополнительно записываются» в БД, а `LoggerPort` объявляет для этого один метод, а не два).

**Outbound:** `AuditPort`
- Назначение: аудит административных действий.
- Кто вызывает: все use case'ы admin, изменяющие состояние (`UploadDocumentUseCase`, `UpdateDocumentUseCase`, `RemoveDocumentUseCase`, `CreateCaseUseCase`, `UpdateCaseUseCase`, `ArchiveCaseUseCase`, `LinkDocumentToCaseUseCase`).
- Кто реализует: `SqliteAuditRepository` (logging_audit/adapters).
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: запись факта действия; вызывается только при успешном завершении действия (docs/04, §1.9) — сам порт это не проверяет, ответственность на вызывающем use case.

**Outbound:** `AnalyticsReadPort`
- Назначение: точка расширения для будущего аналитического модуля (docs/02, §12); в MVP не потребляется никем внутри системы.
- Кто вызывает: в MVP — никто (зарезервировано).
- Кто реализует: `SqliteSystemEventsRepository` (logging_audit/adapters) — тот же класс, что хранит системные события.
- Жизненный цикл: один экземпляр на процесс.
- Ответственность: чтение уже сохранённых `SystemEventEntry`; не создаёт и не изменяет их (создание — через `LoggerPort.log_system_error`, см. выше).

## 2. Полный перечень методов портов

### ConversationPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `handle` | Обработать одно входящее сообщение и вернуть ответ | `IncomingMessage` (user_id, chat_id, text, command, correlation_id) | `OutgoingResponse` (text, requires_confirmation, confirmation_action) | Не выбрасывает наружу — любая внутренняя ошибка (Application/Infrastructure) перехватывается координатором и превращается в нейтральный `OutgoingResponse` (docs/02, §11) |

### ProfileRepositoryPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `get_profile` | Получить единственный профиль | — | `Profile \| None` (`None`, если ещё не создан) | Infrastructure Error при недоступности SQLite |
| `save_profile` | Сохранить профиль при первичной загрузке | `Profile` | — | Infrastructure Error; не предназначен для повторного вызова как «редактирование» (docs/01, §4.3) |

### DialogueHistoryPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `get_recent` | Получить последние реплики диалога | `dialogue_id`, `limit` | `list[DialogueMessage]` | Infrastructure Error |
| `record_user_message` | Создать новую запись реплики пользователя, статус `received` | `dialogue_id`, `text`, `correlation_id` | `DialogueMessage` | Validation Error, если `text` пуст; Infrastructure Error |
| `record_assistant_message` | Создать новую запись ответа ассистента | `dialogue_id`, `text`, `correlation_id` | `DialogueMessage` | Validation Error, если `text` пуст; Infrastructure Error |
| `mark_request_completed` | Перевести статус реплики пользователя в `completed` | `user_message_id` | — | Not Found Error, если запись не существует; Infrastructure Error |
| `mark_request_failed` | Перевести статус реплики пользователя в `failed` | `user_message_id` | — | Not Found Error; Infrastructure Error |

### FactRepositoryPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `stage_draft` | Создать черновик факта; заменяет предыдущий активный черновик того же пользователя (docs/04, §1.3) | `user_id`, `text` | `FactDraft` | Validation Error, если `text` пуст; Infrastructure Error |
| `confirm_draft` | Подтвердить черновик — создать `Fact`, черновик прекращает существование | `draft_id` | `Fact` | Not Found Error, если черновик не существует или истёк (`expires_at` в прошлом); Infrastructure Error |
| `list_confirmed` | Получить подтверждённые факты пользователя | `user_id` | `list[Fact]` | Infrastructure Error |
| `forget` | Удалить подтверждённый факт | `user_id`, `fact_id` | — | Not Found Error либо идемпотентный no-op (см. раздел 9 — контракт не зафиксирован в docs/01–04, выбор в «Замечаниях») |

### DocumentRepositoryPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `add` | Создать запись метаданных документа | `Document` | — | Conflict Error при повторном `document_id`; Infrastructure Error |
| `update` | Обновить метаданные (включая `index_status`) | `Document` | — | Not Found Error; Infrastructure Error |
| `delete` | Удалить запись метаданных | `document_id` | — | Not Found Error либо идемпотентный no-op (см. раздел 9); Infrastructure Error |
| `get` | Получить документ по id | `document_id` | `Document \| None` | Infrastructure Error |
| `list_all` | Получить все документы | — | `list[Document]` | Infrastructure Error |

### CaseRepositoryPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `add` | Создать кейс | `Case` | — | Conflict Error; Infrastructure Error |
| `update` | Обновить кейс | `Case` | — | Not Found Error; Infrastructure Error |
| `archive` | Перевести кейс в `ARCHIVED` | `case_id` | — | Not Found Error; Infrastructure Error |
| `get` | Получить кейс по id | `case_id` | `Case \| None` | Infrastructure Error |
| `list_all` | Получить все кейсы | — | `list[Case]` | Infrastructure Error |
| `link_document` | Связать документ с кейсом | `case_id`, `document_id` | — | Not Found Error, если документ/кейс не существует; идемпотентно при повторной ссылке (docs/04, §1.7 — уникальность пары); Infrastructure Error |
| `unlink_document` | Убрать связь | `case_id`, `document_id` | — | Not Found Error либо идемпотентный no-op (см. раздел 9); Infrastructure Error |
| `list_documents_for_case` | Получить документы, связанные с кейсом | `case_id` | `list[DocumentId]` | Infrastructure Error |

### FileStoragePort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `save` | Сохранить оригинал файла | `document_id`, `content: bytes` | — | Infrastructure Error (нет места на томе, ошибка записи) |
| `read` | Прочитать оригинал файла | `document_id` | `bytes` | Not Found Error, если файла нет; Infrastructure Error |
| `delete` | Удалить оригинал файла | `document_id` | — | Not Found Error либо идемпотентный no-op (см. раздел 9); Infrastructure Error |

### KnowledgeSearchPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `search` | Найти релевантные фрагменты | `query: str`, `top_k: int` | `list[Fragment]` (с заполненным `score`) | External Service Error (Embedding-провайдер или Qdrant недоступны) — обрабатывается вызывающей стороной по правилу docs/02, §11 (не подменять документы общими знаниями модели) |

### IndexingPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `index_document` | Проиндексировать документ заново | `document_id` | — | Not Found Error, если документ не существует; External Service Error (Embedding/Qdrant); документ переводится в `FAILED` при ошибке (docs/04, §1.5) |
| `index_case` | Проиндексировать кейс заново | `case_id` | — | Аналогично `index_document` |
| `remove_from_index` | Удалить фрагменты источника из индекса | `source_type`, `source_id` | — | Идемпотентно (см. раздел 9); External Service Error |

### EmbeddingPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `embed` | Получить вектор текста | `text: str` | `list[float]` | External Service Error (недоступность провайдера, лимиты) |

### VectorStorePort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `upsert` | Записать фрагменты и их векторы | `fragments: list[Fragment]`, `vectors: list[list[float]]` | — | External Service Error (Qdrant недоступен); Validation Error, если длины списков не совпадают |
| `query` | Найти ближайшие векторы | `vector: list[float]`, `top_k: int` | `list[Fragment]` (со `score`) | External Service Error |
| `delete_by_source` | Удалить все фрагменты источника | `source_type`, `source_id` | — | Идемпотентно (см. раздел 9); External Service Error |

### LLMPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `complete` | Сгенерировать ответ по контексту | `LLMRequestContext` (system_instructions, context_sections) | `LLMResponse` (text, provider, model) | External Service Error (недоступность/таймаут/ошибка авторизации активного поставщика); без автоматического повтора и без перехода на резервного поставщика (docs/01, §9) |

### AdminAuthPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `authenticate` | Проверить логин/пароль, выдать токен сессии | `login: str`, `password: str` | `session token: str` | User Error (неверные учётные данные) — без уточнения, что именно неверно (docs/02, §11) |
| `validate_session` | Проверить валидность токена сессии | `session_token: str` | `bool` | Не выбрасывает ошибку — недействительный токен даёт `False` |

### LoggerPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `log_event` | Записать техническое событие | `TechnicalLogEvent` (correlation_id, event, status, occurred_at) | — | Не должен выбрасывать ошибки наружу (логирование не должно ронять основной поток); сбой самого логирования обрабатывается внутри адаптера |
| `log_system_error` | Записать ошибку, требующую анализа | `SystemEventEntry` (correlation_id, description, occurred_at) | — | Аналогично `log_event` |

### AuditPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `record` | Записать факт административного действия | `AuditEntry` (correlation_id, action, occurred_at) | — | Infrastructure Error — в отличие от `LoggerPort`, здесь сбой записи не должен маскироваться молча: аудит — комплаенс-требование (docs/01, §4.8), поэтому ошибку допустимо пробросить вызывающему use case'у |

### AnalyticsReadPort
| Метод | Назначение | Вход | Выход | Допустимые ошибки |
|---|---|---|---|---|
| `read_since` | Получить системные события после указанной точки трассировки | `correlation_id: CorrelationId \| None` | `list[TechnicalLogEvent]` | Infrastructure Error; в MVP не вызывается никем — контракт зафиксирован для будущего аналитического модуля |

## 3. Контракты Repository

| Repository | Хранит | Никогда не хранит | Кто использует | Кто имеет право изменять |
|---|---|---|---|---|
| **ProfileRepository** (`SqliteProfileRepository`) | Единственную запись `Profile` (`style`, `constraints`) | Данные пользователей, факты, историю | `SeedProfileIfMissingUseCase`, `BuildConversationContextUseCase` | Только `SeedProfileIfMissingUseCase`, и только если записи ещё нет |
| **DialogueHistoryRepository** (`SqliteDialogueHistoryRepository`) | Реплики `DialogueMessage` (обе роли, полный текст, статус пользовательских реплик) | Аудит, системные события, содержимое документов | `ProcessUserMessageUseCase`, `BuildConversationContextUseCase` | Только `ProcessUserMessageUseCase` |
| **FactRepository** (`SqliteFactRepository`) | И `FactDraft`, и `Fact` — один класс на оба порта одного и того же жизненного цикла (docs/02, §16.3) | Историю диалога, документы | `StageFactUseCase`, `ConfirmFactUseCase`, `ListFactsUseCase`, `ForgetFactUseCase`, `BuildConversationContextUseCase` (чтение) | Только четыре use case'а memory |
| **FactDraftRepository** | Отдельного класса **нет** — намеренно: `FactDraft` обслуживается тем же `SqliteFactRepository`, что и `Fact`, через один и тот же `FactRepositoryPort` (см. строку выше). Введение отдельного репозитория противоречило бы уже принятому в docs/02 решению | — | — | — |
| **DocumentRepository** (`SqliteDocumentRepository`) | Метаданные документа: `title`, `category`, `tags`, `index_status` | Содержимое файла, векторы, фрагменты | admin use case'ы, `IndexDocumentUseCase` | admin use case'ы (метаданные); `IndexDocumentUseCase` (только `index_status`) |
| **CaseRepository** (`SqliteCaseRepository`) | Кейсы и таблицу связей «документ—кейс» | Содержимое документов, векторы | admin use case'ы, `IndexDocumentUseCase` (чтение) | admin use case'ы |
| **AuditRepository** (`SqliteAuditRepository`) | `AuditEntry` (correlation_id, action, occurred_at) | Содержимое документов, полный текст запросов, факты | admin use case'ы (запись) | Никто — append-only, изменение/удаление не предусмотрены |
| **SystemEventRepository** (`SqliteSystemEventsRepository`) | `SystemEventEntry` | Текст реплик, секреты | `LoggerPort` (запись через `log_system_error`), `AnalyticsReadPort` (чтение) | Только запись через `LoggerPort`; никто не редактирует |
| **VectorStore** (`QdrantVectorStore`) | Текст фрагмента, вектор, `source_type`/`source_id` (в Qdrant) | Оригинал документа целиком, метаданные документа/кейса (title, category и т. п. — они в SQLite) | `SearchFragmentsUseCase`, `IndexDocumentUseCase` | Только `IndexDocumentUseCase` |
| **FileStorage** (`LocalFileStorageAdapter`) | Байты оригинала файла документа | Метаданные, текст фрагментов | `UploadDocumentUseCase`, `RemoveDocumentUseCase`, `IndexDocumentUseCase` (чтение) | `UploadDocumentUseCase` (запись), `RemoveDocumentUseCase` (удаление) |

## 4. Контракты сервисов

Часть названий из примера задания не совпадает с фактическими именами классов — соответствие указано явно, новых классов не вводится.

### DocumentChunker (`search/application/services/chunking.py`)
- Ответственность: разбить текст документа/кейса на фрагменты, пригодные для эмбеддинга.
- Вход: полный текст (`str`).
- Выход: список текстовых фрагментов (`list[str]`).
- Инварианты: не обращается к Qdrant и к `EmbeddingPort`; результат — только текст, без векторов и идентификаторов (`FragmentId` присваивается позже, в `IndexDocumentUseCase`).

### EmbeddingService
- Отдельного класса с таким именем нет. Роль играет **`EmbeddingPort`** (порт) + `YandexGptEmbeddingAdapter`/`OpenAiEmbeddingAdapter` (реализации) — см. раздел 1.5. Использовать это название как синоним `EmbeddingPort` при дальнейшем проектировании.

### LLMService
- Отдельного класса с таким именем нет. Роль играет **`LLMPort`** (порт) + `YandexGptLLMAdapter`/`OpenAiLLMAdapter` (реализации) — см. раздел 1.6.

### PromptRenderer
- Отдельного класса **нет** в утверждённой структуре (`docs/03`). Ответственность «превратить `ConversationContext` в `LLMRequestContext`» на данный момент встроена в `GenerateAssistantResponseUseCase.execute()` — это не отдельный сервис, а один из шагов этого use case. Выделение `PromptRenderer` в отдельный класс — изменение структуры проекта, не входящее в объём этой задачи; отмечено в «Замечаниях архитектора» как возможное будущее уточнение, а не как принятое решение.

### ConversationContextBuilder
- Соответствует **`BuildConversationContextUseCase`** (ai_core).
- Ответственность: собрать `ConversationContext` из профиля, истории, фактов и фрагментов, в порядке приоритета (docs/01, §4.2); определить, зависит ли запрос от документов БЗ, и как реагировать на недоступность поиска (docs/02, §11).
- Вход: `IncomingMessage`.
- Выход: `ConversationContext`.
- Инварианты: не вызывает `LLMPort`; не решает, что делать при недоступности LLM (это `GenerateAssistantResponseUseCase`/координатор).

### ResponseGenerator
- Соответствует **`GenerateAssistantResponseUseCase`** (ai_core).
- Ответственность: конвертировать `ConversationContext` → `LLMRequestContext`, вызвать `LLMPort.complete`.
- Вход: `ConversationContext`.
- Выход: `LLMResponse`.
- Инварианты: не решает состав контекста; не пишет в историю диалога (это делает координатор `ProcessUserMessageUseCase`).

### CommandRouter
- Соответствует **`RouteConversationCommandUseCase`** (ai_core).
- Ответственность: распознать команду `/запомнить`, `/память`, `/забыть` или подтверждение черновика; делегировать memory use case'ам; вернуть готовый `OutgoingResponse` либо `None`, если это не команда.
- Вход: `IncomingMessage`.
- Выход: `OutgoingResponse | None`.
- Инварианты: не знает о профиле, истории, поиске или LLM (докстрока класса в коде).

## 5. Контракты между модулями

| Кто → | Кого вызывает | Через что | Что получает/передаёт | Что запрещено |
|---|---|---|---|---|
| Telegram-адаптер | AI Core | `ConversationPort` | `IncomingMessage` → `OutgoingResponse` | Обращаться к LLM/Qdrant/SQLite напрямую; принимать решения о содержании ответа |
| AI Core | Profile | `ProfileRepositoryPort` | `Profile` | Изменять профиль (нет такого сценария у AI Core) |
| AI Core | Memory (история) | `DialogueHistoryPort` | Реплики `DialogueMessage` | Прямой доступ к SQLite |
| AI Core | Memory (факты, чтение) | `FactRepositoryPort` | Подтверждённые `Fact` | Изменять факты вне подтверждённого сценария |
| AI Core | Memory (команды) | напрямую, конкретные use case'ы (`StageFactUseCase` и др.) — см. раздел 6, исключение из общего правила | `FactDraft`/`Fact`/список фактов | Обращаться к `SqliteFactRepository` напрямую, минуя use case |
| AI Core | Search | `KnowledgeSearchPort` | `list[Fragment]` | Прямой доступ к Qdrant/`EmbeddingPort` |
| AI Core | LLM | `LLMPort` | `LLMResponse` | Знать, какой конкретно поставщик активен |
| AI Core | Logging | `LoggerPort` | — (только запись событий) | Логировать текст реплик или секреты |
| Admin (HTTP) | Admin (use case'ы) | напрямую (нет отдельного порта, раздел 1.7) | Результат операции | Обращаться к репозиториям knowledge_base напрямую, минуя use case admin |
| Admin | Knowledge Base | `DocumentRepositoryPort`/`CaseRepositoryPort`/`FileStoragePort` | `Document`/`Case`/байты файла | Прямой доступ к SQLite/файловой системе |
| Admin | Search (индексация) | `IndexingPort` | — (запускает индексацию) | Обращаться к Qdrant/`EmbeddingPort` напрямую |
| Admin | Logging (аудит) | `AuditPort` | — (запись действия) | Писать аудит в обход порта |
| Admin | Admin (аутентификация) | `AdminAuthPort` | Токен сессии | Хранить пароль/хеш где-либо, кроме переменных окружения |
| Search | Knowledge Base | `DocumentRepositoryPort`/`CaseRepositoryPort`/`FileStoragePort` | Метаданные и содержимое документа/кейса (только чтение) | Изменять метаданные документа, кроме `index_status`; обращаться к Admin |
| Search | Embedding-провайдер | `EmbeddingPort` | Вектор текста | Знать, какой конкретно провайдер активен |
| Search | Qdrant | `VectorStorePort` | Фрагменты/векторы | Прямой доступ к клиенту Qdrant из use case'ов |
| Любой модуль | Logging (технические события) | `LoggerPort` | — | Передавать текст реплик, ключи, пароли, содержимое документов |
| Composition Root | Все модули | Прямой импорт портов и адаптеров | Собранные use case'ы | — (единственное место, где это разрешено) |

## 6. Правила зависимостей по слоям

Повторение уже утверждённых правил из `docs/03`, §5 — без изменений, для удобства при реализации:

- **Domain** не импортирует ничего, кроме stdlib и `shared.domain`. Не знает про `application`.
- **Application** (порты, use case'ы, `application/services/`) импортирует свой `domain`, порты **и use case'ы** других модулей, но никогда `adapters`/`infrastructure` — ни свои, ни чужие. Именно это правило («порты **и** use case'ы») делает законным прямой вызов AI Core → memory use case'ы (раздел 1.3, 1.7) — это не исключение из правил `docs/03`, а прямое им следование.
- **Adapter** реализует порт своего модуля и обращается к конкретной инфраструктуре (`infrastructure.sqlite`, внешний клиент). Не импортирует другой `adapter` — ни из своего, ни из чужого модуля.
- **Repository** (адаптер, реализующий репозиторный порт) не вызывает Use Case — направление зависимости всегда от use case к репозиторию, никогда наоборот. Один Repository не импортирует и не вызывает другой Repository (ни своего модуля, ни чужого) — согласованность между несколькими репозиториями (например, `DocumentRepositoryPort` + `FileStoragePort` + `VectorStorePort` при удалении документа) обеспечивает use case уровня выше (`RemoveDocumentUseCase`), а не сами репозитории друг через друга.
- **Composition Root** — единственное место, которому разрешено нарушать все правила выше одновременно: импортировать порты и адаптеры всех модулей и связывать их.
- Driving-адаптеры (`telegram/adapters`, `admin/adapters/http`) вызывают только `application` (порт или use case) своего/целевого модуля — никогда `adapters` и никогда друг друга.

## 7. Контракты ошибок

Категории — архитектурные, не классы исключений (в коде на сегодня определены только `DomainError` и семейство `ApplicationError`/`NotFoundError`/`ValidationError`/`ConflictError`, `shared/domain/errors.py` и `shared/application/errors.py`; для остальных категорий ниже единой иерархии в коде пока нет — см. «Замечания архитектора»).

| Категория | Где возникает | Кто имеет право обработать | Куда передаётся дальше |
|---|---|---|---|
| **Domain Error** | Внутри доменной сущности при нарушении инварианта (например, попытка создать `Fragment` без `source_id`) | Use case, вызвавший операцию с сущностью | Превращается в `Application Error` (обычно `ValidationError`) либо пробрасывается координатору |
| **Application Error** (`NotFoundError`, `ValidationError`, `ConflictError`) | В use case при нарушении бизнес-правила (черновик истёк, документ не найден, повторный `document_id`) | Вызывающий use case на уровень выше (координатор `ProcessUserMessageUseCase` или admin-use case) | Driving-адаптер (Telegram/HTTP) — для превращения в ответ пользователю/администратору без утечки деталей |
| **Infrastructure Error** | В адаптере при сбое SQLite/файловой системы (недоступна БД, нет места на томе) | Use case, вызвавший порт — решает, деградировать (docs/02, §11) или пробросить дальше | `LoggerPort.log_system_error` (техническая запись) → нейтральный ответ пользователю/администратору |
| **External Service Error** | В адаптере при сбое внешнего провайдера (YandexGPT/OpenAI как LLM или Embedding, Qdrant) | Use case, вызвавший порт (`GenerateAssistantResponseUseCase`, `SearchFragmentsUseCase`, `IndexDocumentUseCase`) — правила реакции уже зафиксированы в docs/02, §11 | `LoggerPort` (техническая запись) → нейтральный ответ; для индексации — перевод `Document.index_status` в `FAILED` |
| **Validation Error** | На входе use case'а или порта — данные не прошли проверку до операции (пустой текст факта, несовпадение длин списков в `VectorStorePort.upsert`) | Тот же use case, синхронно, до обращения к любому порту | Driving-адаптер — сообщение пользователю/администратору о некорректном вводе |
| **User Error** | На уровне взаимодействия с пользователем/администратором, не связана с состоянием системы (неверный пароль администратора, некорректная команда Telegram) | Driving-адаптер или use case, ближайший к вводу (`AuthenticateAdminUseCase`, `RouteConversationCommandUseCase`) | Ответ пользователю/администратору напрямую — не требует технического журналирования как ошибки (кроме факта неудачной попытки аутентификации, docs/02, §11) |

Общее правило (docs/02, §11): ни пользователю, ни администратору не показываются технические детали ошибки — только нейтральный текст; подробности — только в техническом журнале, без чувствительных данных.

## 8. Контракты транзакций (границы атомарности)

Не описывается механизм (SQL-транзакции, двухфазные операции) — только то, какой use case отвечает за согласованность результата.

| Операция | Что должно быть согласовано | Ответственный Use Case |
|---|---|---|
| Обработка сообщения пользователя | Реплика пользователя (`received`) → результат обработки → статус (`completed`/`failed`) + (при успехе) реплика ассистента | `ProcessUserMessageUseCase` |
| Подтверждение факта | Черновик прекращает существование одновременно с появлением `Fact` — снаружи не должно быть видно промежуточного состояния «и черновик, и факт существуют» либо «ни того, ни другого» | `ConfirmFactUseCase` |
| Создание черновика при уже существующем активном | Старый черновик заменяется новым как одна операция (docs/04, §1.3) | `StageFactUseCase` (через `FactRepositoryPort.stage_draft`) |
| Загрузка документа | Файл в файловом хранилище + запись метаданных со статусом `PENDING` — не должно возникать метаданных без файла | `UploadDocumentUseCase` |
| Индексация документа/кейса | Разбиение на фрагменты + получение векторов + запись в Qdrant + обновление `index_status` — при частичном сбое не должно быть видно частично записанного набора фрагментов (docs/04, §1.5) | `IndexDocumentUseCase` |
| Удаление документа | Метаданные (SQLite) + фрагменты (Qdrant) + файл (файловое хранилище) удаляются согласованно — не должно оставаться «осиротевших» фрагментов или файла без метаданных | `RemoveDocumentUseCase` |
| Создание/обновление кейса | Запись кейса + (при необходимости) переиндексация — согласованность между текстовыми полями кейса и его фрагментами | `CreateCaseUseCase`/`UpdateCaseUseCase` |
| Связывание документа с кейсом | Запись связи — атомарна сама по себе (одна запись, докс/04 §1.7) | `LinkDocumentToCaseUseCase` |
| Административное действие + аудит | Изменение состояния (документ/кейс) должно быть выполнено раньше записи в `AuditPort` — аудит фиксирует только успешные действия (docs/01, §4.8) | Каждый изменяющий use case admin — самостоятельно, перед вызовом `AuditPort.record` |

## 9. Идемпотентность

| Операция | Ожидаемое поведение при повторном выполнении |
|---|---|
| Повторная индексация документа/кейса (`IndexingPort.index_document`/`index_case`) | Безопасна: старый набор фрагментов источника удаляется, создаётся новый (docs/04, §1.8). Повторный вызов не должен приводить к накоплению дублирующихся фрагментов в Qdrant |
| Повторное подтверждение факта (`confirm_draft` с тем же `draft_id` дважды) | Второй вызов не должен создавать второй `Fact` — черновик после первого подтверждения уже не существует, поэтому второй вызов завершается `Not Found Error`, а не тихим повторным созданием |
| Повторная запись `/запомнить` при уже существующем черновике | Не «повтор одной и той же операции», а замена — уже описано как инвариант (docs/04, §1.3), не ошибка |
| Повторное удаление уже удалённой сущности (`forget`, `DocumentRepositoryPort.delete`, `CaseRepositoryPort.unlink_document`, `FileStoragePort.delete`, `VectorStorePort.delete_by_source`) | Контракт не зафиксирован явно в docs/01–04. Для MVP рекомендуется идемпотентное поведение (повторное удаление уже отсутствующей записи — не ошибка, а no-op), кроме случаев, где отсутствие записи означает ошибку вызывающей стороны, — решение вынесено в «Замечания архитектора» |
| Повторная загрузка документа с тем же содержимым/названием | Создаёт **новый**, отдельный `Document` с новым `document_id` — в модели нет естественного ключа уникальности по названию/содержимому (docs/04 не вводит такого инварианта). Указано как открытый вопрос, если требуется дедупликация — не в объёме MVP |
| Повторный запуск обработки одного и того же входящего сообщения (например, повторная доставка обновления Telegram) | Контракт не зафиксирован — `ConversationPort.handle` не имеет встроенной защиты от дублирования по `correlation_id`/update-идентификатору; повторный вызов создаст вторую пару `DialogueMessage` и повторно обратится к LLM. Отмечено как открытый вопрос в «Замечаниях архитектора», не решается самостоятельно на уровне логической модели |

## 10. Контракты AI Core — последовательность вызовов координатора

`ProcessUserMessageUseCase.handle(message)`:

1. Вызывает `DialogueHistoryPort.record_user_message` — создаёт реплику пользователя со статусом `received`.
2. Вызывает `RouteConversationCommandUseCase.route(message)`.
   - Если возвращён `OutgoingResponse` (сообщение было командой `/запомнить`, `/память`, `/забыть` или подтверждением) — координатор вызывает `DialogueHistoryPort.mark_request_completed` и возвращает этот ответ. Дальнейшие шаги не выполняются.
   - Если возвращён `None` — переход к шагу 3.
3. Вызывает `BuildConversationContextUseCase.execute(message)`, получает `ConversationContext`.
4. Вызывает `GenerateAssistantResponseUseCase.execute(context)`, получает `LLMResponse`.
5. Вызывает `DialogueHistoryPort.record_assistant_message` — создаёт новую запись ответа ассистента.
6. Вызывает `DialogueHistoryPort.mark_request_completed` для исходной реплики пользователя.
7. Вызывает `LoggerPort.log_event` — фиксирует использованного поставщика/модель и `correlation_id`/статус (без текста).
8. Возвращает `OutgoingResponse`, построенный из текста `LLMResponse`.

**При исключении на шагах 3–5** (Application/Infrastructure/External Service Error): координатор вызывает `DialogueHistoryPort.mark_request_failed`, вызывает `LoggerPort.log_system_error` (или `log_event`, в зависимости от категории ошибки — раздел 7), возвращает нейтральный `OutgoingResponse` (docs/02, §11). Шаг 5 (запись ответа ассистента) в этом случае не выполняется — реплика ассистента создаётся только при успехе (docs/04, §1.2).

Координатор не содержит правил приоритета источников контекста (это `BuildConversationContextUseCase`) и не формирует промпт (это `GenerateAssistantResponseUseCase`) — он только последовательно вызывает шаги и отвечает за статус реплики.

## 11. Контракты Search — взаимодействие с Knowledge Base и AI Core

**С AI Core:** Search получает от AI Core только текстовый запрос и `top_k` (через `KnowledgeSearchPort.search`); возвращает `list[Fragment]` с заполненным `score`. Search не получает от AI Core ни профиля, ни истории диалога, ни фактов — приоритет источников контекста Search не касается (это ответственность `BuildConversationContextUseCase`). Search не имеет права обращаться к `ProfileRepositoryPort`, `DialogueHistoryPort` или `FactRepositoryPort`.

**С Knowledge Base:** Search читает `Document`/`Case` (метаданные и содержимое через `FileStoragePort`) исключительно внутри `IndexDocumentUseCase`, и только на чтение — за исключением одного разрешённого исключения: обновления `Document.index_status` через `DocumentRepositoryPort.update()` по результату индексации (docs/03, §6). Search не имеет права изменять `title`, `category`, `tags` документа, создавать/удалять/архивировать `Case`, создавать `DocumentCaseLink`.

**Что Search не имеет права делать:**
- Обращаться к Qdrant или к Embedding-провайдеру в обход `VectorStorePort`/`EmbeddingPort`.
- Инициировать собственную индексацию без вызова через `IndexingPort` (то есть Search не «слушает» изменения Knowledge Base самостоятельно — индексацию всегда запускает Admin, docs/02 §6).
- Писать в `AuditPort` — аудит фиксирует только действия администратора, инициированные через Admin, а не факт индексации сам по себе.
- Обращаться к `admin`-модулю в любом виде.

## 12. Контракты Logging

| | Обязано логироваться | Запрещено логировать | CorrelationId |
|---|---|---|---|
| **TechnicalLogEvent** | Факт обработки запроса, длительность операций, состояние интеграций с провайдерами, использованный LLM-поставщик и модель (docs/01, §4.2, §4.8) | Текст реплик, ключи API, пароли, содержимое документов, полные запросы к модели без необходимости, токены Telegram, персональные данные в открытом виде (docs/01, §4.8) | Присутствует в каждой записи; используется только для сопоставления записей одного запроса при диагностике — не является внешним ключом (docs/04, §2) |
| **AuditEntry** | Факт успешного административного действия (загрузка/изменение/удаление документа или кейса) — не сами данные документа | Содержимое документа/кейса, чувствительные данные | Присутствует, может совпадать с `correlation_id` инициировавшего HTTP-запроса; не используется как ссылка на конкретную запись `Document`/`Case` (для этого есть `document_id`/`case_id` в самом действии, не в `AuditEntry`) |
| **SystemEventEntry** | Ошибка, требующая последующего анализа (сбой LLM/Embedding/Qdrant/SQLite, ошибка индексации) | Аналогично TechnicalLogEvent — без текста реплик, секретов, содержимого документов | Присутствует; единственная точка, доступная на чтение через `AnalyticsReadPort` для будущего аналитического модуля (docs/02, §12) |

`CorrelationId` формируется на входе в систему (в момент получения сообщения Telegram-адаптером либо HTTP-запроса панели администратора) и передаётся неизменным через все use case'ы одной операции — это единственный способ связать `DialogueMessage`, `TechnicalLogEvent`, `SystemEventEntry` и `AuditEntry` одного запроса при разборе инцидента, не являясь при этом связью в смысле модели данных (докс/04, §2).

## 13. Контракты инфраструктуры

| Внешняя зависимость | Через какой порт | Примечание |
|---|---|---|
| Telegram Bot API | **Без порта.** Telegram — driving-сторона: он не «вызывается через выходной порт», а сам инициирует вызов `ConversationPort` через `telegram/adapters`. Ответ пользователю отправляет тот же адаптер, не через отдельный outbound-порт | Единственная внешняя зависимость, о которой AI Core не имеет ни малейшего представления, — весь Telegram-специфичный код изолирован в `modules/telegram` |
| YandexGPT / OpenAI (генеративная модель) | `LLMPort` | Выбор активного поставщика — `LLM_PROVIDER`/`LLM_MODEL`, независимо от эмбеддингов (docs/02, §16.2) |
| YandexGPT / OpenAI (эмбеддинги) | `EmbeddingPort` | Отдельная конфигурация `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL` — тот же физический провайдер, но другой порт и другой выбор |
| Qdrant | `VectorStorePort` | Единственная точка входа — `QdrantVectorStore`; ни один другой компонент клиента Qdrant не импортирует |
| SQLite | Не единый порт — каждый репозиторный порт (`ProfileRepositoryPort`, `DialogueHistoryPort`, `FactRepositoryPort`, `DocumentRepositoryPort`, `CaseRepositoryPort`, `AuditPort`, `AnalyticsReadPort`) отвечает за свою часть данных; физическое соединение — только через `SqliteConnectionFactory` (`infrastructure/sqlite/connection.py`) | Ни один порт не открывает файл БД в обход фабрики соединения (docs/03, §11) |
| Файловая система (постоянный том) | `FileStoragePort` | Единственный потребитель — `LocalFileStorageAdapter` |
| HTTP (транспорт панели администратора) | **Без порта** — как и Telegram, это driving-сторона (`admin/adapters/http`), а не внешняя зависимость, вызываемая изнутри системы | Не следует путать с `AdminAuthPort` — тот описывает аутентификацию, а не транспорт |

## 14. Проверка архитектуры

1. **Все Use Case используют только порты.** В основном — да. Документированное исключение: `RouteConversationCommandUseCase` (ai_core) вызывает конкретные use case'ы memory (`StageFactUseCase` и др.) напрямую, без промежуточного порта — разрешено правилом `docs/03`, §5 («application импортирует... порты **и, где есть, use cases**»); раздел 6 этого документа фиксирует это явно как не-нарушение, а описанный случай.
2. **Ни один Adapter не вызывается напрямую (в обход порта).** Подтверждено — все use case'ы получают адаптеры только как реализацию своего порта через composition root; ни один файл `application/` не импортирует чужой `adapters/*`.
3. **Отсутствуют циклические зависимости.** Подтверждено на уровне графа модулей (`docs/03`, §6/§15): `ai_core → llm, memory, profile, search, logging_audit`; `search → knowledge_base`; `admin → knowledge_base, search, logging_audit`; `telegram → ai_core, logging_audit`. Обратных рёбер нет.
4. **Нет Repository, который знает другой Repository.** Подтверждено — ни один `*_repository.py`/`*_adapter.py` не импортирует другой файл из чужого `adapters/`. Согласованность между несколькими репозиториями обеспечивают use case'ы (раздел 8), а не сами репозитории.
5. **Domain не зависит от Infrastructure.** Подтверждено — ни один файл `domain/` не импортирует `adapters`, `infrastructure` или сторонние библиотеки (docs/03, §15, статическая проверка).
6. **Все взаимодействия проходят через интерфейсы.** С одной точной оговоркой: межмодульные взаимодействия проходят через **application-контракты** — это либо `Protocol`-порт (когда реализаций может быть больше одной или того требует изоляция инфраструктуры), либо конкретный use case другого модуля (когда реализация ровно одна и это не инфраструктура) — оба варианта официально допустимы `docs/03`, §5. Ни одно взаимодействие не идёт в обход обоих этих механизмов напрямую к чужому `adapters/*`.
7. **Нет противоречий docs/01–04.** Обнаруженные неоднозначности не разрешены самостоятельно и не привели к изменению docs/01–04 — они перечислены в «Замечаниях архитектора» ниже (отсутствие адаптера `AdminAuthPort`, отсутствие класса `PromptRenderer`, идемпотентность `forget`/`delete`/`unlink`, дедупликация повторной доставки сообщения, отсутствие естественного ключа уникальности документа).

## Результат

### Изменённые файлы
- Создан: `docs/05_internal_interfaces.md` (этот документ).
- `docs/01–04` и код в `src/dekoder/` не изменялись.

### Перечень всех портов (16)
`ConversationPort`, `ProfileRepositoryPort`, `DialogueHistoryPort`, `FactRepositoryPort`, `DocumentRepositoryPort`, `CaseRepositoryPort`, `FileStoragePort`, `KnowledgeSearchPort`, `IndexingPort`, `EmbeddingPort`, `VectorStorePort`, `LLMPort`, `AdminAuthPort`, `LoggerPort`, `AuditPort`, `AnalyticsReadPort`.

### Перечень Repository (9 физических классов на 10 запрошенных ролей)
`SqliteProfileRepository`, `SqliteDialogueHistoryRepository`, `SqliteFactRepository` (обслуживает и `FactRepository`, и `FactDraftRepository`), `SqliteDocumentRepository`, `SqliteCaseRepository`, `SqliteAuditRepository`, `SqliteSystemEventsRepository`, `QdrantVectorStore`, `LocalFileStorageAdapter`.

### Перечень сервисов
`DocumentChunker` (существует как есть); `RouteConversationCommandUseCase` (= CommandRouter), `BuildConversationContextUseCase` (= ConversationContextBuilder), `GenerateAssistantResponseUseCase` (= ResponseGenerator) — все три существуют как use case'ы ai_core, не как отдельный сервисный слой; `EmbeddingPort`/`LLMPort` (= EmbeddingService/LLMService — порты, не сервисы); `PromptRenderer` — не выделен отдельным классом (раздел 4).

### Перечень внутренних интерфейсов
16 портов (см. выше) + 2 «интерфейса без формального порта» (memory use case'ы, вызываемые ai_core напрямую; admin use case'ы, вызываемые HTTP-роутами напрямую) — оба зафиксированы как легитимные по правилу `docs/03`, §5.

### Архитектурные проверки
Все 7 пунктов раздела 14 — пройдены, с одной документированной (не нарушающей) особенностью: прямые вызовы use case'ов между `ai_core`↔`memory` и внутри `admin` вместо портов, явно разрешённые `docs/03`, §5.

### Замечания архитектора

1. **Реализация `AdminAuthPort` отсутствует в утверждённой структуре.** `docs/03` не содержит файла-адаптера, реализующего `AdminAuthPort` (сравнение пароля с `ADMIN_PASSWORD_HASH`). Вероятное расположение — новый файл в `admin/adapters/` — но его создание меняет структуру проекта, что не входит в объём этой задачи. Зафиксировано как открытый вопрос, а не решено самостоятельно.
2. **`PromptRenderer` как отдельный класс не существует.** Ответственность встроена в `GenerateAssistantResponseUseCase`. Выделение в отдельный сервис возможно в будущем, но не сделано сейчас — это тоже изменение структуры.
3. **Идемпотентность операций удаления (`forget`, `DocumentRepositoryPort.delete`, `CaseRepositoryPort.unlink_document`, `FileStoragePort.delete`, `VectorStorePort.delete_by_source`) не зафиксирована в docs/01–04.** Рекомендован (не предписан) идемпотентный вариант — повторное удаление отсутствующей записи не считается ошибкой; окончательное решение уместно принять при проектировании конкретных репозиториев.
4. **Дедупликация повторной доставки одного и того же входящего сообщения не описана нигде в docs/01–04.** `ConversationPort.handle` не имеет встроенной защиты — при повторной доставке (типичный сценарий для Telegram webhook) будет создана вторая пара `DialogueMessage` и повторно вызвана языковая модель. Требует решения на этапе реализации Telegram-адаптера или `ProcessUserMessageUseCase`, не решается на уровне логической модели.
5. **У `Document` нет естественного ключа уникальности** (по названию или содержимому) — повторная загрузка того же файла создаёт второй, отдельный документ. Не описано в docs/01–04 как проблема; отмечено на случай, если для реализации потребуется дедупликация.
6. **`LoggerPort.log_system_error` подразумевает запись в два места одновременно** (stdout/stderr и `SystemEventRepository`), хотя порт формально объявляет один метод у одного адаптера (`StdoutTechnicalLogger`). Контракт явно зафиксирован в разделах 1.8 и 3 этого документа как «два побочных эффекта одного вызова», чтобы реализация не расходилась в этом вопросе.
7. **Единая иерархия исключений для категорий Infrastructure/External Service/User Error отсутствует в коде** — определены только `DomainError` и `ApplicationError`-семейство (`NotFoundError`, `ValidationError`, `ConflictError`). Раздел 7 описывает архитектуру категорий, не вводя новых классов, как и требовалось; если единая иерархия понадобится, это отдельное решение вне объёма текущей задачи.


