# Continue Thin Client AI для 1C AI Workbench

Гибридные профили для слабого Windows-ноутбука (ориентир — 16 ГБ RAM).
Облачная **или локальная** LLM рассуждает, ведёт чат и применяет правки; локально
работают IDE, существующие точные MCP-индексы и лёгкое автодополнение.

С v1 профили provider-neutral — «принеси свой ключ или свою модель» (BYOK/BYOM):
подойдёт любой OpenAI-compatible провайдер. Groq-профиль `OnlineHybrid` сохранён
как необязательный legacy preset.

## Архитектурный принцип

- Agent-модель (облачная или локальная) выполняет chat / edit / apply и
  рассуждение в Agent-режиме. Модель должна поддерживать tool calling
  (capability `tool_use`) для вызова MCP.
- Локально: точный Code Index MCP (`bsl-indexer`) и Help Index MCP (Синтаксис-помощник).
- Локальное автодополнение: отдельная лёгкая Ollama-модель `qwen2.5-coder:1.5b-base`.
- Без второго RAG, без векторной БД, без локального embedding pipeline.

## Профили

### Online Hybrid

```yaml
models:
  - Groq openai/gpt-oss-120b        # роли: chat, edit, apply; capabilities: tool_use
  - Groq qwen/qwen3.6-27b (Preview) # роли: chat, edit, apply; capabilities: tool_use
  - Ollama qwen2.5-coder:1.5b-base  # роль: autocomplete (локально)
mcpServers:
  - 1c-code-index  # bsl-indexer serve, точный поиск по коду 1С
  - 1c-help-index  # Python .venv, HELP_INDEX_MODE=readonly
```

Облачные модели получают роли `chat`, `edit`, `apply` и capability `tool_use`
(нужна для Agent-режима и вызова MCP). Ollama-модель получает только `autocomplete`.
Ключ Groq хранится как секрет Continue: `${{ secrets.GROQ_API_KEY }}`.

Оба шаблона используют Continue `schema: v1`: роли находятся внутри каждого
`models[]`, MCP-серверы — в `mcpServers`, а Agent tool calling объявлен через
`capabilities: [tool_use]`. Устаревшие плоские model-role поля не используются.

### Offline Lite — autocomplete only

```yaml
models:
  - Ollama qwen2.5-coder:1.5b-base  # роль: autocomplete (локально)
```

Честные ограничения Offline Lite:

- только автодополнение; нет chat/edit/apply;
- нет `mcpServers` — профиль не вызывает Code/Help Index MCP самостоятельно;
- нет Groq и любого облачного провайдера, нет облачных URL, нет API-ключей;
- это не полноценный локальный AI-агент.

Для работы с локальными MCP-индексами нужен HostedAgent, LocalAgent, Online Hybrid
(с моделью для рассуждения) либо отдельный MCP-клиент.

## Provider-neutral профили (BYOK / BYOM)

Эти профили принимают любого OpenAI-compatible провайдера. Ключ моделируется только
**именем** Continue-секрета (`${{ secrets.<NAME> }}`); значение ключа никогда не
принимается параметром, не печатается и не встраивается.

### HostedAgent (облачная модель оператора)

```yaml
models:
  - provider: openai          # одна OpenAI-compatible HTTPS-модель оператора
    model: <user model id>    # роли: chat, edit, apply; capabilities: tool_use
    apiKey: ${{ secrets.<NAME> }}
    apiBase: <https endpoint>
  - Ollama qwen2.5-coder:1.5b-base  # роль: autocomplete (локально)
mcpServers:
  - 1c-code-index  # bsl-indexer serve
  - 1c-help-index  # readonly
```

Модель получает роли `chat`, `edit`, `apply` и capability `tool_use`. apiBase обязан
быть HTTPS без userinfo/query/fragment. `Preset` подставляет проверенный endpoint,
имя секрета и (необязательно) модель:

| Preset | apiBase | Имя секрета | Модель по умолчанию |
| --- | --- | --- | --- |
| `generic` | требуется `-ApiBase` | требуется `-SecretName` | требуется `-ModelId` |
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | требуется `-ModelId` |
| `zai` | `https://api.z.ai/api/paas/v4` | `ZAI_API_KEY` | `glm-4.6` |
| `groq-legacy` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | `openai/gpt-oss-120b` |

Z.AI endpoint (`https://api.z.ai/api/paas/v4`) и модель `glm-4.6` проверены по
официальной документации Z.AI перед включением preset.

```powershell
# Полностью из preset
.\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent -Preset zai

# Generic: свой endpoint, модель и имя секрета
.\scripts\28_prepare_continue_profile.ps1 -Profile HostedAgent `
    -ApiBase https://api.openai.com/v1 -ModelId gpt-4o-mini -SecretName OPENAI_API_KEY
```

### LocalAgent (полностью офлайн, своя модель)

```yaml
models:
  - provider: openai          # локальная tool-capable OpenAI-compatible модель
    model: <local model id>   # роли: chat, edit, apply; capabilities: tool_use
    apiBase: <loopback http>/v1  # OpenAI-compatible API; 127.0.0.1 / localhost / ::1
  - Ollama qwen2.5-coder:1.5b-base  # роль: autocomplete (локально)
mcpServers:
  - 1c-code-index
  - 1c-help-index  # readonly
```

- HTTP разрешён только для loopback; облачные URL, секреты и `apiKey` запрещены.
- Модель обязана поддерживать tool calling (`tool_use`) — без него Agent-режим
  невозможен.
- Endpoint локального агента по умолчанию использует authority эффективного
  `OLLAMA_HOST` и добавляет обязательный `/v1`. Ollama-автодополнение использует
  тот же authority без `/v1`; переопределить агент можно через
  `-LocalAgentApiBase`.

```powershell
.\scripts\28_prepare_continue_profile.ps1 -Profile LocalAgent -LocalAgentModel qwen2.5-coder:7b
# свой локальный OpenAI-compatible endpoint агента (loopback + /v1)
.\scripts\28_prepare_continue_profile.ps1 -Profile LocalAgent -LocalAgentModel qwen2.5-coder:7b `
    -LocalAgentApiBase http://127.0.0.1:8080/v1
```

### Escape hatch: своя конфигурация Continue

Продвинутый оператор может не использовать генератор и подключить собственный
`~/.continue/config.yaml`. При этом остаются в силе правила безопасности
(`.continue/rules/1c-workbench.md`), `.continueignore`, read-only Help MCP и
ответственность за ключи. Генератор не пишет в пользовательский `~/.continue`.

## Почему без embeddings и LanceDB

Точные индексы уже существуют: `bsl-indexer` даёт структурный поиск по коду 1С,
Help Index MCP — FTS5-поиск по справке. Для слабого ноутбука дублирующий векторный
индекс означает дополнительный расход RAM и времени индексации без доказанного
выигрыша в качестве поиска. Векторный слой можно рассмотреть позже и только после
отдельного golden-retrieval сравнения. В текущем профиле его нет.

## Требования и RAM

Ориентир — 16 ГБ RAM. Контрольный снимок на тестовом Windows-хосте 2026-07-28
под загруженной `qwen2.5-coder:1.5b-base`: 15.3 ГБ всего, 13.6 ГБ занято,
1.7 ГБ свободно; `llama-server` working set 1108.3 МБ и private 1222.0 МБ,
VS Code working set 2574.6 МБ. Это host-specific measurement, а не гарантия:
перед merge и на целевой машине измерение повторяется вместе с полным live-профилем.

## Генерация и проверка профилей

Генератор подставляет абсолютные пути вместо шаблонов и пишет детерминированный
UTF-8 (без BOM, LF) только в `<RepoRoot>/generated/continue/`. Относительный
`-OutputPath` вычисляется от этого каталога; абсолютный путь допустим только внутри
него. Нормализация пути и запрет существующих junction/symlink/reparse-компонентов
выполняются до проверки `-Force` и повторно перед записью. При `-Force` существующая
directory entry сначала удаляется, а новый файл открывается через `CreateNew`:
NTFS hard link не может перенаправить запись во внешний файл, а конкурентная
подстановка destination приводит к отказу. Поэтому `..`, абсолютный путь,
reparse point, hard link или `-Force` не могут вывести запись за границу.

Перед любой записью тот же статический валидатор получает отрендерованный YAML
в памяти (UTF-8 в base64 для совместимости с Windows PowerShell 5.1) и проверяет
его семантический контракт. Поэтому `-CheckOnly` выполняет реальный YAML
parse/semantic validation, но не создаёт файл, каталог или временный профиль.
Генератор не принимает, не печатает и не встраивает API-ключ и не пишет в
пользовательский `~/.continue`.

При успешном `-CheckOnly` exit code равен `0`, а stdout содержит краткое
`Semantic validation: PASS` и целевой путь. При ошибке exit code ненулевой, детали
валидатора идут в stderr, output-файл не создаётся. Поведение границы покрыто
`tests/test_continue_profiles.py`, MCP handshake — `tests/test_mcp_stdio_probe.py`.

```powershell
# Online Hybrid
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid

# Offline Lite
.\scripts\28_prepare_continue_profile.ps1 -Profile OfflineLite

# Только проверка (без записи)
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -CheckOnly

# Перезапись существующего файла
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -Force

# Строгая проверка полного локального runtime (ненулевой exit, если чего-то нет)
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -RequireRuntimeReady
```

`-RequireRuntimeReady` проверяет установленный Continue для VS Code, поддерживаемый
Continue dotenv-источник Groq secret, release `bsl-indexer`, source mirror и
`CODE_INDEX_HOME`, проектный Python, Help DB, реальный MCP
`initialize`/`tools/list` для Code MCP и readonly Help MCP, а также Ollama service и
точный тег `qwen2.5-coder:1.5b-base` через тот же локальный API endpoint, который
записан в Continue profile. Для Offline Lite проверяются Continue, точный Ollama
endpoint и модель.

Статический валидатор можно также вызвать для записанного файла:

```powershell
python .\scripts\29_validate_continue_profile.py --kind online --config .\generated\continue\online-hybrid.yaml
python .\scripts\29_validate_continue_profile.py --kind offline --config .\generated\continue\offline-lite.yaml
```

## Настройка GROQ_API_KEY

В профиле используется только ссылка `${{ secrets.GROQ_API_KEY }}`. Для IDE Continue
разрешает секреты в следующем порядке:

1. `<workspace-root>/.env`;
2. `<workspace-root>/.continue/.env`;
3. `%USERPROFILE%/.continue/.env`.

Process environment — четвёртый источник только для Continue CLI. VS Code/JetBrains
extension не читает shell environment, поэтому один `$env:GROQ_API_KEY` не проходит
IDE-oriented `-RequireRuntimeReady`. См. официальные
[Continue secret resolution rules](https://docs.continue.dev/faqs#where-secrets-are-resolved-from).

- Не коммитьте `.env` и любые файлы с реальным ключом.
- Не вставляйте реальное значение ключа в YAML-профиль.
- Readiness-проверка определяет только наличие непустой dotenv-записи; значение ключа
  не печатается, не передаётся дочерним probe-процессам и не встраивается в YAML.

## Ollama-модель (вручную)

Автодополнение использует локальную модель. Загрузите её вручную (скрипты профиля
модели не скачивают):

```powershell
ollama pull qwen2.5-coder:1.5b-base
```

Генератор читает эффективный `OLLAMA_HOST` (по умолчанию
`127.0.0.1:11434`), нормализует его в `apiBase` и принимает только явный
loopback HTTP endpoint: `127.0.0.1`, `localhost` или `::1`. Это важно для
Windows Ollama app, которая может использовать локальный порт `11534`.
Для Ollama autocomplete path запрещён; для OpenAI-compatible LocalAgent требуется
ровно `/v1`. Удалённый host, HTTPS, credentials, query или fragment отклоняются:
Offline Lite не может незаметно превратиться в сетевой профиль.

Для нестандартного локального порта задайте endpoint до генерации и подтвердите,
что в сгенерированном YAML появился тот же `apiBase`:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11534"
.\scripts\28_prepare_continue_profile.ps1 -Profile OfflineLite -CheckOnly -RequireRuntimeReady
```

## Установка Continue (вручную)

Установка и подключение Continue — ручной шаг. Скрипты профиля не устанавливают
Continue, Ollama, Java и не меняют глобальный конфиг Continue. Сгенерированный
`generated/continue/*.yaml` оператор подключает к Continue самостоятельно по
документации Continue.

## Источник .hbk

Help Index MCP работает по локальной базе Синтаксис-помощника, собранной из `.hbk`
установленной платформы 1С. Источник `.hbk` должен быть законным и локальным
(собственная установленная платформа 1С). Файлы `.hbk` и SQLite-база индекса не
коммитятся (см. `.gitignore` и `.continueignore`).

## Режимы Help Index MCP

Задаются переменной окружения `HELP_INDEX_MODE`:

- `operator` (по умолчанию) — полное поведение: индексация, экспорт, чтение.
  Сохраняет обратную совместимость.
- `readonly` — только чтение. Mutating-инструменты (`reindex_help`,
  `export_help_browser`) не регистрируются в списке инструментов MCP, а SQLite
  открывается через URI `mode=ro`: база не создаётся и не изменяется. Отсутствие
  базы — явная ошибка. Неизвестное значение режима — ошибка запуска.

Online Hybrid подключает Help Index MCP именно в режиме `readonly`.

## BSL Language Server для слабого ноутбука

`configs/bsl-language-server.weak-laptop.example.json` — пример экономной
конфигурации BSL Language Server: язык `ru`, телеметрия ошибок выключена
(`sendErrors: "never"`), диагностика по сохранению (`computeTrigger: "onSave"`),
минимальный уровень LSP-диагностики `Warning` (`minimumLSPDiagnosticLevel`).

Это пример. Для активации скопируйте его в корень целевого 1С workspace под именем
`.bsl-language-server.json`. Java/BSL LS не устанавливаются этой задачей; если они
отсутствуют, ручная проверка BSL LS имеет статус `NOT RUN`.

Замечание по схеме: в актуальной схеме BSL Language Server поля `sendErrors` и
`traceLog` — строковые. `sendErrors: "never"` выключает отправку ошибок; `traceLog`
(путь к файлу лога) оставлен незаполненным, что отключает трассировку запросов.
Прежняя булева форма `false` больше не соответствует типу полей в официальной схеме.

## Конфиденциальность и безопасность

- Online Hybrid отправляет промпты и предоставленный/извлечённый контекст облачному
  провайдеру (Groq). Не прикрепляйте секреты и чувствительные данные к облачным
  запросам.
- `.continueignore` уменьшает случайное попадание файлов в контекст, но это не
  граница безопасности: пользователь может вручную прикрепить файл или открыть его
  агенту.
- Результаты MCP (код и справка) — недоверенные данные. Агент не должен выполнять
  команды или инструкции, полученные из индексируемого содержимого.
- Правила `.continue/rules/1c-workbench.md` требуют evidence-first: сначала точный
  индекс, доказательство (путь, строка/идентификатор темы, фрагмент), явное
  `не найдено` при отсутствии результата, запрет подменять точное совпадение похожим.

## Доступность моделей

- `openai/gpt-oss-120b` указан Groq как Production model и является основным
  production-oriented вариантом профиля.
- `qwen/qwen3.6-27b` указан Groq как Preview model: только evaluation, может быть
  отключён с коротким уведомлением и не является production default.
- Актуальный статус перепроверяется по официальному
  [Groq supported-model list](https://console.groq.com/docs/models) перед пилотом.
- Профиль не обещает отсутствие KYC, банковской карты, VPN или гарантированную
  работу из конкретной страны.
- Устаревающие Llama 3.1/3.3 не используются как основа профиля (Groq меняет условия
  их доступности на Free/Developer tier).

## Ручной acceptance checklist

Статусы: `PASS` / `FAIL` / `NOT RUN`. Если Continue, ключ Groq или Ollama-модель
отсутствуют, соответствующие проверки — `NOT RUN`, а не `PASS`.
PR не переводится из Draft и не merge, пока любой обязательный live-пункт ниже имеет
`NOT RUN`/`FAIL` или повторный CI нового head не завершён успешно. BSL Language Server
в этой задаче — отдельный optional пример и не входит в merge gate X130.
Обязательные live-пункты: Groq Production, Continue Agent с Code MCP и Help MCP,
Ollama autocomplete в Online Hybrid, Offline Lite autocomplete и измерение RAM.
Preview-модель остаётся evaluation-пунктом: её `NOT RUN` не блокирует merge, если
Production-модель прошла.

| Проверка | Статус |
| --- | --- |
| Генератор Online Hybrid создаёт валидный YAML без неразрешённых токенов | PASS (pytest) |
| Генератор Offline Lite создаёт валидный YAML | PASS (pytest) |
| Генератор HostedAgent создаёт валидный YAML (preset + generic) | PASS (pytest) |
| Генератор LocalAgent создаёт валидный YAML | PASS (pytest) |
| Provider/model/secret matrix (preset×model×secret) | PASS (pytest) |
| Malicious endpoint rejection (http remote, missing `/v1`, creds/query/fragment, non-loopback) | PASS (pytest) |
| Literal-secret rejection как `-SecretName`/`-ModelId`/`-ApiBase` | PASS (pytest) |
| Local/cloud isolation (no apiKey, no secret, no cloud host) | PASS (pytest) |
| Exact roles/tool_use и Code/Help MCP contract для HostedAgent/LocalAgent | PASS (pytest) |
| CheckOnly без записи для всех профилей | PASS (pytest) |
| Backward-compat: OnlineHybrid/OfflineLite неизменны | PASS (pytest) |
| Валидатор принимает все четыре профиля | PASS (pytest) |
| Help MCP readonly: mutating-тулы отсутствуют, SQLite mode=ro, hash/mtime неизменны | PASS (pytest) |
| PRISM eval: точный символ, путь, строка, evidence token | PASS (CI + локально 7/7) |
| PRISM: рядом существует `РассчитатьСумму`, но запрос `РассчитатьСумма` возвращает пустой retrieval | PASS (CI + локально 7/7) |
| PRISM: полностью отсутствующий `НесуществующийМетод` возвращает пустой retrieval | PASS (CI + локально 7/7) |
| `.continue/rules/1c-workbench.md` и корневой `.continueignore` существуют | PASS (pytest) |
| BSL example — валидный JSON, диагностика по onSave | PASS (pytest) |
| Повторный CI на текущем PR head | PASS (2026-07-28: 11/11 required checks; после любого push проверяется заново) |
| Continue открыл Online Hybrid и ответил через Groq | FAIL (2026-07-28: профиль загружен; запрос Groq получил HTTP 403 от текущей сети) |
| Groq `openai/gpt-oss-120b` Production отвечает | FAIL (2026-07-28: HTTP 403 `Access denied`; ключ найден локально, значение не журналируется) |
| Groq `qwen/qwen3.6-27b` Preview доступен как selectable evaluation model | NOT RUN (основной Groq-запрос заблокирован сетью) |
| HostedAgent (preset zai) отвечает через проверенный Z.AI endpoint | NOT RUN (live acceptance — задача Codex) |
| HostedAgent (generic OpenAI-compatible) отвечает на выбранном провайдере | NOT RUN (live acceptance — задача Codex) |
| LocalAgent: локальная tool-capable модель отвечает и вызывает MCP | NOT RUN (live acceptance — задача Codex) |
| HostedAgent/LocalAgent Continue Agent вызывает Code MCP и Help MCP | NOT RUN (live acceptance — задача Codex; stdio initialize + tools/list PASS) |
| Continue Agent вызывает Code MCP и получает evidence | NOT RUN (stdio initialize + tools/list PASS; вызов из Agent не выполнен из-за Groq 403) |
| Continue Agent вызывает readonly Help MCP и получает evidence | NOT RUN (stdio initialize + tools/list PASS; вызов из Agent не выполнен из-за Groq 403) |
| Ollama autocomplete работает с `qwen2.5-coder:1.5b-base` | NOT RUN (модель и прямой `/api/generate` PASS; запрос из IDE в журнале Ollama не подтверждён) |
| Offline Lite работает без cloud/MCP и даёт локальное autocomplete | NOT RUN (профиль и runtime readiness PASS; транспорт IDE → Ollama не подтверждён) |
| BSL Language Server активирован и выдаёт диагностику по onSave | NOT RUN (Java/BSL LS отсутствуют) |
| Измерение RAM под локальной моделью | PASS (2026-07-28: 15.3 ГБ всего, 13.6 ГБ занято, 1.7 ГБ свободно; `llama-server` working set 1108.3 МБ, private 1222.0 МБ; VS Code working set 2574.6 МБ) |

### Evidence и разбор live-ошибок

Воспроизводимые локальные проверки:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\26_run_prism_eval.py
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -CheckOnly -RequireRuntimeReady
.\scripts\28_prepare_continue_profile.ps1 -Profile OfflineLite -CheckOnly -RequireRuntimeReady
```

Для autocomplete одного успешного прямого `/api/generate` недостаточно: во время
ввода в IDE должен появиться новый запрос в Ollama и применимая inline-подсказка.
Для Code/Help MCP одного `initialize`/`tools/list` недостаточно: обязательный gate —
вызов инструмента из Continue Agent с evidence в ответе.

При Groq HTTP 403 сначала выполните безопасный triage без печати ключа: проверьте,
что secret загружен из поддерживаемого Continue dotenv-файла; проверьте разрешение
модели в Groq organization/project settings; повторите минимальный запрос из другой
разрешённой сети. Не меняйте статус на `PASS`, пока запрос из Continue не ответил
и Agent не вызвал оба MCP.
