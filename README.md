# 1C AI Workbench

[![release](https://img.shields.io/github/v/release/timoshinoleg-eng/1c-ai-workbench?include_prereleases&sort=semver)](https://github.com/timoshinoleg-eng/1c-ai-workbench/releases)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![reuse](https://img.shields.io/badge/REUSE-compliant-brightgreen.svg)](REUSE.toml)

**1C AI Workbench** — локальный read-only AI/MCP-инструментарий для навигации, аудита и анализа конфигураций **1С:Предприятие 8.3**.

Проект зеркалирует XML-выгрузку 1С, индексирует BSL-код и метаданные локально и предоставляет MCP-инструменты для совместимых клиентов: OpenCode, Cursor, VS Code, desktop MCP clients и других stdio-MCP клиентов.

Главная идея: **evidence-first анализ без необходимости отдавать конфигурацию 1С внешнему сервису**. По умолчанию Workbench не изменяет исходную выгрузку, не подключается к live-базе и не включает write-операции.

## Статус

Проект готов для локальных read-only сценариев и контролируемых пилотов.

| Проверка | Текущий результат |
| --- | --- |
| Healthcheck | `6/6 Ready` |
| Python test suite | `68 passed` in Linux CI preflight |
| E2E smoke | `PASS 8 / FAIL 0 / SKIP 1` |
| Rust indexer | `bsl-indexer.exe`, 25.6 MB |
| Release model | signed candidate → clean Windows verification → publish verified artifact |

Публичный production-release проходит отдельный двухфазный signed-candidate процесс. Контракт выпуска описан в [docs/RELEASE_CONTRACT_V1.md](docs/RELEASE_CONTRACT_V1.md).

## Для чего нужен Workbench

Типовые вопросы, которые проект помогает разбирать по реальным артефактам конфигурации:

- где записывается конкретный регистр;
- какому объекту принадлежит форма или модуль;
- какие процедуры и функции экспортирует модуль;
- какие объекты метаданных дублируются, пусты или требуют проверки;
- что изменилось между двумя выгрузками;
- где именно разработчику проверить вывод в Конфигураторе или EDT;
- какие участки кода участвуют в конкретном потоке выполнения.

Ответы должны содержать не только вывод, но и путь к исходному файлу, объект 1С, процедуру/функцию, evidence snippet, уровень уверенности и шаги ручной проверки.

## Архитектура

```text
XML-выгрузка 1С
  C:\1c-ai-client\dump
        |
        | read-only mirror
        v
generated\index\source-mirror
        |
        | local indexing
        v
code-index-mcp
  Rust MCP server + SQLite index
        |
        +--> skills-bridge
        |    Python/FastMCP, read-only 1C skills
        |
        +--> prompt-gallery
        |    callable MCP prompts
        |
        +--> help-index-mcp
        |    local .hbk help search
        |
        +--> ibcmd-bridge
        |    experimental Phase B, disabled by default
        |
        v
MCP client
  OpenCode / Cursor / VS Code / desktop MCP client
```

## Основные компоненты

| Компонент | Назначение |
| --- | --- |
| `1c-code-index` | Rust MCP-сервер для BSL/code metadata и локального SQLite-индекса |
| `1c-skills` | FastMCP bridge с 1C-specific read-only инструментами |
| `1c-prompt-gallery` | MCP-обёртка над проверенными prompt-сценариями |
| `1c-help-index` | локальный поиск по справке 1С через SQLite FTS5 |
| `1c-ibcmd` | экспериментальный bridge; write-path выключен по умолчанию |

## Быстрый старт

### Требования

- Windows 10/11;
- PowerShell 5.1+;
- Git for Windows;
- Python 3.10+;
- XML-выгрузка конфигурации 1С;
- подписанный release artifact с prebuilt `bsl-indexer.exe` либо Rust toolchain для локальной сборки.

### Установка и проверка

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
cd <workbench-root>

.\scripts\setup.ps1
.\scripts\16_check_skills_bridge.ps1
.\scripts\17_check_ibcmd_bridge.ps1
.\scripts\18_check_prompt_gallery.ps1
.\scripts\04_index_1c_dump.ps1 -DumpRoot "C:\1c-ai-client\dump" -Force
.\scripts\06_healthcheck.ps1
.\scripts\22_run_e2e_smoke.ps1 -DumpRoot "C:\1c-ai-client\dump" -SkipIndex
```

После первичной настройки можно использовать интерактивный launcher:

```powershell
.\START_HERE.ps1
```

`scripts/setup.ps1` создаёт `.venv`, устанавливает зависимости bridge-серверов и принимает только зафиксированную версию `code-index 0.45.0`. Автозагрузка разрешена только при явных `-ReleaseTag` и `-IndexerSha256`; отсутствие pin приводит к fail-closed поведению.

## MCP-серверы

### 1C Code Index

```powershell
.\tools\code-index-mcp\target\release\bsl-indexer.exe serve --path onec=.\generated\index\source-mirror --transport stdio
```

### 1C Skills

Read-only bridge с 16 специализированными инструментами, включая `meta_info`, `form_info`, `skd_info`, `role_info`, `cf_info`.

```powershell
.\scripts\16_check_skills_bridge.ps1
```

### Prompt Gallery

Публикует каждый `prompts/*.md` как callable MCP-инструмент. В публичном наборе есть `explain-module`, `find-object`, `review-bsl`, `trace-flow`.

```powershell
.\scripts\18_check_prompt_gallery.ps1
```

### Help Index

Индексирует локальные `.hbk`-файлы установленной платформы 1С в SQLite FTS5 и предоставляет поиск без отправки справочного корпуса наружу.

### IBCMD Bridge

Экспериментальный Phase B bridge. Write-операции блокируются, пока одновременно не заданы `IBCMD_ALLOW_WRITE=1` и явное подтверждение `confirm_replace=true`.

```powershell
.\scripts\17_check_ibcmd_bridge.ps1
```

## Контракт ответа AI

Хороший ответ должен включать:

1. короткий вывод;
2. имя и тип объекта 1С;
3. путь внутри `generated/index/source-mirror`;
4. модуль, процедуру или функцию;
5. evidence snippet;
6. уровень уверенности;
7. шаги ручной проверки в Конфигураторе или EDT.

Глобальные правила для AI-агентов находятся в [AI_RULES.md](AI_RULES.md). Path-scoped правила расположены в `rules/`.

## Безопасность и приватность

Базовая модель безопасности:

- работа с локальной зеркальной копией XML-выгрузки;
- read-only режим по умолчанию;
- отсутствие автоматической телеметрии и выгрузки исходников;
- generated indexes, logs и reports остаются локальными;
- API-ключи принадлежат оператору и не встраиваются в Workbench;
- проприетарные бинарники 1С не распространяются вместе с проектом;
- live/write flows через `ibcmd` отключены по умолчанию;
- BSL/XML содержимое рассматривается как данные, а не как инструкции для AI-агента.

Подробнее: [SECURITY.md](SECURITY.md) и [docs/SECURITY_OVERVIEW.md](docs/SECURITY_OVERVIEW.md).

## Release engineering

Production assets публикуются только после:

1. сборки и подписи release candidate;
2. проверки тех же файлов на чистом Windows-хосте;
3. публикации проверенных бинарников без повторной сборки.

Это снижает риск расхождения между протестированным и опубликованным артефактом. Подробности: [docs/RELEASE_CONTRACT_V1.md](docs/RELEASE_CONTRACT_V1.md).

## GitVerse + Cloud.ru pilot

В репозитории подготовлен тестовый GitVerse CI workflow для российского cloud toolchain:

```text
GitVerse
   |
   | CI / validation
   v
Cloud.ru project
9dcd962b-a943-4762-9b53-51ad3da59415
   |
   +--> Artifact Registry   (следующий этап)
   +--> Container Apps      (следующий этап)
   +--> AI Agents / MCP     (пилотный сценарий)
```

Workflow находится в `.gitverse/workflows/cloudru-ci.yml`.

Текущий этап **не разворачивает платные ресурсы автоматически**. CI проверяет код и конфигурацию cloud target. Для перехода к Artifact Registry / Container Apps потребуется добавить защищённые GitVerse secrets. Инструкция: [docs/GITVERSE_CLOUDRU.md](docs/GITVERSE_CLOUDRU.md).

## Коммерческие пилоты

Публичный read-only engine распространяется под MIT. Для коммерческих пилотов могут отдельно предоставляться:

- premium prompts;
- golden answers / evaluation sets;
- enterprise security playbook;
- acceptance methodology;
- integration workflow;
- named support.

Подробнее: [docs/COMMERCIAL.md](docs/COMMERCIAL.md).

## Демо

```powershell
.\scripts\11_open_demo_showcase.ps1
```

Материалы: `demo-showcase/`, `demo-questions/`, `demo-answers/`.

## Лицензирование и происхождение компонентов

Проект распространяется под лицензией [MIT](LICENSE). Карта атрибуции и границы заимствований описаны в [docs/legal/BORROWING_MAP.md](docs/legal/BORROWING_MAP.md).

Ключевые upstream-проекты:

- `cc-1c-skills` — Nikolay-Shirokov, MIT;
- BSL Language Server;
- OneScript;
- Vanessa Runner.

## Документация

- `START_HERE.ps1` — интерактивная точка входа для Windows;
- [AI_RULES.md](AI_RULES.md) — правила для AI-агентов;
- [SECURITY.md](SECURITY.md) — threat model и hard defaults;
- [docs/RELEASE_CONTRACT_V1.md](docs/RELEASE_CONTRACT_V1.md) — release process;
- [docs/GITVERSE_CLOUDRU.md](docs/GITVERSE_CLOUDRU.md) — GitVerse/Cloud.ru CI pilot;
- [CHANGELOG.md](CHANGELOG.md) — история изменений.

---

**1C AI Workbench** строится как безопасный evidence-first слой между кодовой базой 1С и современными AI/MCP-клиентами, а не как автономный генератор изменений в production-конфигурации.
