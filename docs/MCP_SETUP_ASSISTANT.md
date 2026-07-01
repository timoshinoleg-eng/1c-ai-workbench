# MCP Setup Assistant

Короткий маршрут, если локальный индекс уже готов и нужно подключить внешний клиент без ручного блуждания по нескольким документам.

## Что должно быть готово заранее

1. Выгрузка 1С уже проиндексирована.
2. `scripts\06_healthcheck.ps1` проходит без ошибок.
3. Есть readiness-report:

```text
C:\1c-ai-workbench\generated\reports\readiness-report.html
```

Если `External Client = Blocked`, сначала исправьте это по readiness-report.

## Какой клиент выбрать

### opencode

Если нужен самый короткий сценарий для локального пилота.

- Используйте:
  - `opencode.jsonc`
  - `docs\OPENCODE_SETUP_RU.md`
- Проверка:

```powershell
cd C:\1c-ai-workbench
opencode mcp list
```

Ожидаемо:

```text
1c-code-index connected
```

### Внешний MCP-клиент

Если нужен режим внешнего клиента через совместимый endpoint.

> Внимание: автоматические установщики внешних клиентов не входят в production v1 contract. Используйте только ручную настройку по документации выбранного клиента и только по явному согласию оператора.

- Установите Node.js 18+ LTS вручную (официальный установщик с nodejs.org).
- Установите выбранный внешний MCP-клиент вручную, если он нужен.
- Подготовьте API-ключ провайдера внешнего клиента.
- Создайте локальный пользовательский config по документации выбранного клиента.
- После настройки снова прогоните:

```powershell
.\scripts\06_healthcheck.ps1 -OpenReport
```

### Cursor / VS Code / desktop MCP client

Если клиент уже выбран командой или партнёром.

- Используйте шаблоны из:

```text
configs\
```

- Смотрите:

```text
configs\README_MCP_CONFIGS.md
```

## Минимальный путь подключения

1. Запустить readiness check:

```powershell
.\scripts\06_healthcheck.ps1 -OpenReport
```

2. Если индекс и MCP готовы:
   - открыть `docs\OPENCODE_SETUP_RU.md` для opencode
   - или `docs\API_KEY_SETUP.md` для внешнего MCP-клиента, Cursor или VS Code

3. Подключить MCP server:

```text
C:\1c-ai-workbench\tools\code-index-mcp\target\release\bsl-indexer.exe
```

Args:

```text
serve --path onec=C:\1c-ai-workbench\generated\index\source-mirror --transport stdio
```

Env:

```text
CODE_INDEX_HOME=C:\1c-ai-workbench\generated\code-index-home
```

## Первый smoke после подключения

Задайте не общий вопрос, а один из role-based packs:

- `demo-questions\questions_basic.md`
- `demo-questions\questions_1c_lead.md`
- `demo-questions\questions_developer_workflow.md`
- `demo-questions\questions_partner_demo.md`

И требуйте формат:

```text
Назови конкретный файл, найденное место, уверенность и как проверить руками.
Если точного места нет — скажи это прямо.
```

## Если хотите самый короткий сценарий

1. `START_HERE.ps1`
2. Пункт `1` — readiness dashboard
3. Пункт `17` — First 10 Minutes
4. Пункт `18` — MCP Setup Assistant
5. Пункт `4` — local search smoke

После этого пользователь уже не идёт вслепую.
