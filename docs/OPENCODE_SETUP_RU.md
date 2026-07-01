# Настройка opencode для 1C AI Dev Workbench

## Когда нужен opencode

opencode нужен, если вы хотите задавать вопросы AI-клиенту через MCP-инструмент `1c-code-index`. Для проверки без AI можно использовать локальный поиск из `START_HERE.ps1` или команду `search-text`.

## Перед настройкой

Выполните:

```powershell
cd C:\1c-ai-workbench
.\scripts\06_healthcheck.ps1
```

Должен быть итог:

```text
[OK] Summary: 6 checks passed, 0 failed.
```

## MCP-команда

Рабочий локальный сервер запускается так:

```powershell
C:\1c-ai-workbench\tools\code-index-mcp\target\release\bsl-indexer.exe serve --path onec=C:\1c-ai-workbench\generated\index\source-mirror --transport stdio
```

Переменная окружения:

```powershell
CODE_INDEX_HOME=C:\1c-ai-workbench\generated\code-index-home
```

## Настройка в opencode

1. Откройте PowerShell.
2. Выполните:

```powershell
opencode mcp add
```

3. Название сервера: `1c-code-index`.
4. Command: путь к `bsl-indexer.exe` выше.
5. Args: `serve --path onec=C:\1c-ai-workbench\generated\index\source-mirror --transport stdio`.
6. Env: `CODE_INDEX_HOME=C:\1c-ai-workbench\generated\code-index-home`.

Проверьте:

```powershell
opencode mcp list
opencode mcp debug 1c-code-index
```

Если ваша версия opencode поддерживает project config, можно запускать из корневой папки 1C AI Dev Workbench:

```powershell
opencode --config C:\1c-ai-workbench\opencode.jsonc
```

## Если opencode не установлен

Проверьте локальный индекс без AI:

```powershell
cd C:\1c-ai-workbench
.\tools\code-index-mcp\target\release\bsl-indexer.exe search-text "Контрагенты" --path "C:\1c-ai-workbench\generated\index\source-mirror" --limit 5
```

Если вывод содержит локальные пути под `generated\index\source-mirror`, индекс работает.

## API-ключ

API-ключ вводится в настройках выбранного AI-провайдера/opencode. Не записывайте ключ в README, архивы, скриншоты или Git. Для пилота используйте ключ клиента или временный ключ с лимитом и отзывом после теста. Подробно: `docs\API_KEY_SETUP.md`.
