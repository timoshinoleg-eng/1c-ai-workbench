# 1C AI Workbench

[![release](https://img.shields.io/github/v/release/timoshinoleg-eng/1c-ai-workbench?include_prereleases&sort=semver)](https://github.com/timoshinoleg-eng/1c-ai-workbench/releases)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![reuse](https://img.shields.io/badge/reuse-compliant-brightgreen.svg)](REUSE.toml)

Локальный read-only AI workbench для навигации, аудита и анализа конфигураций
1C:Enterprise 8.3 через MCP-совместимые клиенты.

Workbench зеркалирует XML-выгрузку 1С, локально индексирует BSL-код и
метаданные, а затем отдаёт структурированные MCP-инструменты в opencode,
Cursor, VS Code, desktop MCP client или любой клиент, поддерживающий stdio
MCP-серверы.

Production assets публикуются только после двухфазного signed-candidate
процесса: сборка и подпись, проверка тех же файлов на чистой Windows, затем
публикация без пересборки. Контракт процесса описан в
[`docs/RELEASE_CONTRACT_V1.md`](docs/RELEASE_CONTRACT_V1.md).

## Текущий статус

Workbench готов для локального read-only использования.

| Метрика | Цель | Факт |
| --- | --- | --- |
| `scripts/06_healthcheck.ps1` | 6/6 Ready | 6/6 Ready |
| `python -m pytest -q` | all green | Run in CI on every pull request and push |
| `scripts/22_run_e2e_smoke.ps1 -SkipIndex` | all green | PASS: 8 / FAIL: 0 / SKIP: 1 |
| `bsl-indexer.exe` (Rust) | built & in release | 25.6 MB |

## Что решает

Командам 1С часто нужны быстрые ответы на вопросы:

- где записывается этот регистр;
- какому объекту принадлежит форма или модуль;
- какие процедуры экспортирует модуль;
- какие объекты метаданных дублируются, пустые или подозрительные;
- что изменилось между двумя выгрузками конфигурации;
- где разработчику вручную проверить найденное место.

1C AI Workbench даёт внешнему клиенту локальные доказательства, а не заставляет
внешний сервис угадывать по обрывкам кода.

## Архитектура

```text
XML-выгрузка 1С
  C:\1c-ai-client\dump
        |
        | read-only зеркало
        v
source mirror
  generated\index\source-mirror
        |
        | индексируется bsl-indexer
        v
code-index-mcp
  Rust MCP server + SQLite index
        |
        +--> skills-bridge       Python/FastMCP, read-only 1C skills
        +--> prompt-gallery      Python/FastMCP, callable prompts
        +--> help-index-mcp      Python/FastMCP, local .hbk help search
        +--> ibcmd-bridge        Python/FastMCP, Phase B, disabled by default
        |
        v
MCP client
  opencode / Cursor / VS Code / desktop MCP client
```

Все дефолтные сценарии работают с экспортированными файлами или с generated
mirror. Исходная выгрузка не изменяется, live write path не включается
автоматически.

## Требования

- Windows 10/11.
- PowerShell 5.1+.
- Git for Windows.
- Python 3.10+ для Python MCP bridges.
- Подписанный installer с prebuilt `bsl-indexer.exe`, проверенный release artifact
  либо Rust toolchain для сборки индексатора из исходников.
- Файлы выгрузки конфигурации 1С в `C:\1c-ai-client\dump`.
- Опционально: Rust toolchain с `cargo` и `rustc`, если нужно пересобрать
  `bsl-indexer` из исходников.

`scripts\setup.ps1` создаёт `.venv`, ставит зависимости bridge-серверов и
принимает только `code-index 0.45.0`. Автозагрузка разрешается лишь с явно
переданными `-ReleaseTag` и `-IndexerSha256`; отсутствующий pin падает закрыто.

## Быстрый старт

Сначала прочитайте [инструкцию первого запуска в корпоративной среде](docs/ENTERPRISE_FIRST_RUN.md). Не отключайте ExecutionPolicy глобально. Если политика CurrentUser не управляется доменом, предпочтительный вариант:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
cd <workbench-root>
.\scripts\setup.ps1
.\scripts\16_check_skills_bridge.ps1
.\scripts\17_check_ibcmd_bridge.ps1
.\scripts\18_check_prompt_gallery.ps1
.\scripts\04_index_1c_dump.ps1 -DumpRoot "C:\1c-ai-client\dump" -Force
.\scripts\06_healthcheck.ps1
.\scripts\22_run_e2e_smoke.ps1 -DumpRoot "C:\1c-ai-client\dump" -SkipIndex
```

После этого можно открыть интерактивный launcher:

```powershell
.\START_HERE.ps1
```

Ручной путь:

```powershell
cd <workbench-root>
.\scripts\setup.ps1
.\scripts\01_check_env.ps1
.\scripts\02_clone_repos.ps1
.\scripts\04_index_1c_dump.ps1 -DumpRoot "C:\1c-ai-client\dump" -Force
.\scripts\06_healthcheck.ps1
```

`scripts\03_build_bsl_indexer.ps1` нужен только разработчикам, которым нужно
пересобрать Rust-бинарник локально вместо использования release artifact. Порядок проверки release artifact, SHA-256, версии и подписи описан в [release evidence guide](docs/RELEASE_EVIDENCE.md). Назначение всех команд разделено в [script catalog](docs/SCRIPT_CATALOG.md).

## MCP-серверы

### `1c-code-index`

Основной Rust MCP-сервер. Индексирует и отдаёт BSL/code metadata. Перед планированием новых search/metadata tools сверьтесь с [feature-gap map](docs/FEATURE_GAP_MAP.md), чтобы не дублировать возможности текущего индексатора.

```powershell
.\tools\code-index-mcp\target\release\bsl-indexer.exe serve --path onec=.\generated\index\source-mirror --transport stdio
```

### `1c-skills`

Python FastMCP bridge для read-only 1C-specific skills: 16 инструментов
(`meta_info`, `form_info`, `skd_info`, `role_info`, `cf_info`, и др.).

```powershell
.\scripts\16_check_skills_bridge.ps1
```

### `1c-prompt-gallery`

Python FastMCP bridge, публикующий каждый `prompts/*.md` как callable
MCP-инструмент. Публичные prompts: `explain-module`, `find-object`,
`review-bsl`, `trace-flow`.

```powershell
.\scripts\18_check_prompt_gallery.ps1
```

### `1c-help-index`

Python FastMCP bridge для локальной справки 1С. Индексирует `.hbk` файлы из
установленной платформы 1С в SQLite FTS5.

### `1c-ibcmd`

Экспериментальный Phase B bridge для утилиты `ibcmd`. По умолчанию выключен.
Write operations заблокированы без `IBCMD_ALLOW_WRITE=1` и `confirm_replace=true`.

```powershell
.\scripts\17_check_ibcmd_bridge.ps1
```

## Проверка

```powershell
.\scripts\16_check_skills_bridge.ps1
.\scripts\17_check_ibcmd_bridge.ps1
.\scripts\18_check_prompt_gallery.ps1
.\scripts\06_healthcheck.ps1
```

## Контракт ответа AI

Хороший ответ должен содержать:

1. короткий вывод;
2. имя и тип объекта 1С;
3. путь к файлу внутри `generated\index\source-mirror`;
4. модуль, процедуру или функцию, если найдены;
5. evidence snippet;
6. уровень уверенности;
7. шаги ручной проверки в Конфигураторе или EDT.

## Демо

```powershell
.\scripts\11_open_demo_showcase.ps1
```

Демо-материалы: `demo-showcase\index.html`, `demo-questions\questions_basic.md`.

## Модель безопасности

- Дефолтный режим локальный и read-only.
- Source dump зеркалируется перед индексацией.
- Generated indexes и logs остаются внутри локальной папки workbench.
- API keys принадлежат клиенту/оператору и настраиваются ими.
- Проприетарные бинарники 1С не бандлятся.
- `ibcmd` live/write flows выключены по умолчанию.

## Лицензии и атрибуция

Репозиторий распространяется под MIT (см. [LICENSE](LICENSE)). Атрибуция и
границы заимствований описаны в `docs/legal/BORROWING_MAP.md`.

Ключевые источники:

- `cc-1c-skills` от Nikolay-Shirokov, MIT
- BSL Language Server
- OneScript
- Vanessa Runner

## Commercial

Commercial pilots (premium prompts, golden answers, enterprise playbook,
named support) are available from the maintainer. See [docs/COMMERCIAL.md](docs/COMMERCIAL.md), [pilot runbook](docs/PILOT_RUNBOOK.md) and [technical acceptance checklist](docs/PILOT_ACCEPTANCE_CHECKLIST.md).
