## ADR: 003 — Prompt Gallery MCP

**Статус:** accepted

**Контекст:**
Prompt gallery существует как набор Markdown-файлов в `prompts/`, но MCP-клиенты
не могут обнаружить и вызвать эти prompts как инструменты. Из-за этого правила и
операционные сценарии применяются только вручную, когда пользователь копирует
prompt в чат.

**Рассмотренные варианты:**
1. Вариант A — оставить prompts как файлы и документировать ручное копирование.
2. Вариант B — сделать отдельный FastMCP wrapper, который регистрирует каждый
   `prompts/*.md` как callable tool.
3. Вариант C — встроить prompts в `code-index-mcp`.

**Решение:** Вариант B — `tools/prompt-gallery/server.py`.

**Обоснование:**
Отдельный MCP-сервер сохраняет Prompt Gallery как agent-layer компонент,
не добавляет markdown-логику в Rust indexer и автоматически подхватывает новые
`.md` файлы. Инструменты возвращают prompt contract с контекстом вызова, а не
пытаются дублировать analyzer/runtime логику.

**Последствия:**
- Добавлен `tools/prompt-gallery/`.
- Добавлен check script `scripts/18_check_prompt_gallery.ps1`.
- Добавлена integration card `docs/phase-a/integration-cards/prompt-gallery.md`.
- Добавлена MCP entry `1c-prompt-gallery` в `opencode.jsonc`.
- Prompt count теперь определяется live-директорией `prompts/*.md`.

**Compliance с BORROWING_MAP:**
- Есть ли заимствование? нет, используются локальные prompts проекта.
- Если да — указана ли лицензия? не применимо.
- Нарушает ли границы? нет, сервер read-only и не меняет исходники.
