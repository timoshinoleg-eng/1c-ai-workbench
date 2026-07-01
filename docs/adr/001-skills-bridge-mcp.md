## ADR: 001 — Skills Bridge MCP

**Статус:** accepted

**Контекст:**
`1c-ai-workbench` уже имеет read-only `code-index-mcp`, но prompt/skill layer не
вызывается как MCP-инструменты. Нужно обернуть P0-навыки из `cc-1c-skills` в
callable-интерфейс без live mode и без дублирования `code-index-mcp`.

**Рассмотренные варианты:**
1. Вариант A — вызывать оригинальные PowerShell/Python scripts из
   `cc-1c-skills` напрямую.
2. Вариант B — написать FastMCP bridge, который читает `source-mirror`
   напрямую и адаптирует read-only логику навыков.
3. Вариант C — встроить навыки в `code-index-mcp`.

**Решение:** Вариант B — отдельный Python FastMCP server
`tools/skills-bridge/server.py`.

**Обоснование:**
Отдельный MCP-сервер сохраняет границу P0 read-only, не связывает Rust
`code-index-mcp` с Python-зависимостями и отключается одной настройкой в
`opencode.jsonc`. Прямой парсинг XML/BSL дает fallback, когда `code-index-mcp`
недоступен.

**Последствия:**
- Добавлен `tools/skills-bridge/` с 10 MCP tools.
- Добавлен check script `scripts/16_check_skills_bridge.ps1`.
- Добавлена integration card `docs/phase-a/integration-cards/skills-bridge.md`.
- Добавлена optional MCP entry в `opencode.jsonc`.

**Compliance с BORROWING_MAP:**
- Есть ли заимствование? да, адаптация идей `cc-1c-skills`.
- Если да — указана ли лицензия? да, MIT в `ATTRIBUTION.md` и integration card.
- Нарушает ли границы? нет, код не копирует оригинальные scripts и работает
  read-only по source-mirror.
