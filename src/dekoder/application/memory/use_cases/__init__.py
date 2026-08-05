"""
Use case'ы долговременной памяти (Sprint 5, задача S5-05):
`CreateMemoryRecord`, `ConfirmMemoryRecord`, `RejectMemoryRecord`,
`ListMemoryRecords`, `DeleteMemoryRecord`.

`UpdateMemoryRecord` (упомянут §13.6 «Плана реализации.md») сознательно
НЕ реализуется в Sprint 5 — нет ни одного вызывающего сценария без
административного интерфейса (Этап 10, `backlog_5.md` §1 «В Sprint 5 не
входят»): ни Telegram (`/remember` создаёт запись сразу `CONFIRMED`,
ADR-5.9, без последующего редактирования текста/категории), ни use
case'ы этого пакета не нуждаются в изменении уже сохранённой записи —
только в смене статуса (`ConfirmMemoryRecord`/`RejectMemoryRecord`) или
удалении (`DeleteMemoryRecord`). Это осознанный пропуск (YAGNI), не
недосмотр — при появлении Этапа 10 `UpdateMemoryRecord` добавляется без
изменения формы `MemoryRecord`/порта `MemoryRepository`.
"""

from __future__ import annotations
