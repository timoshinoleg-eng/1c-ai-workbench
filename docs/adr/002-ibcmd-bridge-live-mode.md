## ADR: 002 — ibcmd Bridge Live Mode

**Статус:** proposed

**Контекст:**
Workbench Phase A работает по read-only XML dump. Для Phase B нужен
контролируемый способ получать свежую конфигурацию из реальной ИБ и готовить
EDT/project flows без COM Eval и без ручного Configurator export.

**Рассмотренные варианты:**
1. Вариант A — вызывать `ibcmd` вручную из runbook.
2. Вариант B — сделать отдельный MCP wrapper вокруг `ibcmd`, выключенный по
   умолчанию и безопасный по write-gate.
3. Вариант C — встроить `ibcmd` вызовы в `code-index-mcp`.

**Решение:** Вариант B — `tools/ibcmd-bridge/server.py`.

**Обоснование:**
Отдельный MCP-сервер сохраняет границу Phase B, не добавляет proprietary
зависимость в Rust indexer, отключается одной настройкой и дает dry-run перед
любой live-командой. Экспорт конфигурации допустим как первый live-flow;
обновление индекса выполняется отдельным tool flow, сравнение делается по двум
XML-выгрузкам, а импорт требует `IBCMD_ALLOW_WRITE=1` и `confirm_replace=true`.

**Последствия:**
- Добавлен experimental MCP server `tools/ibcmd-bridge`.
- Добавлен check script `scripts/17_check_ibcmd_bridge.ps1`.
- Добавлена integration card `docs/phase-a/integration-cards/ibcmd-bridge.md`.
- Добавлена disabled MCP entry в `opencode.jsonc`.
- Добавлены read-only flows `ibcmd_export_and_index` и `ibcmd_compare_exports`.
- `ibcmd.exe` не бандлится и должен быть установлен отдельно.

**Compliance с BORROWING_MAP:**
- Есть ли заимствование? нет кода; есть интеграция с внешней proprietary CLI.
- Если да — указана ли лицензия? источник и границы указаны в integration card.
- Нарушает ли границы? нет, бинарник не поставляется, live mode отключен по
  умолчанию, write-операции gated.
