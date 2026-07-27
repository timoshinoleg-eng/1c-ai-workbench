# Continue Thin Client AI для 1C AI Workbench

Гибридный профиль для слабого Windows-ноутбука (ориентир — 16 ГБ RAM).
Облачная LLM рассуждает, ведёт чат и применяет правки; локально работают только
IDE, существующие точные MCP-индексы и лёгкое автодополнение.

## Архитектурный принцип

- Облако (Groq) выполняет chat / edit / apply и рассуждение в Agent-режиме.
- Локально: точный Code Index MCP (`bsl-indexer`) и Help Index MCP (Синтаксис-помощник).
- Локальное автодополнение: Ollama `qwen2.5-coder:1.5b-base` (только autocomplete).
- Без второго RAG, без векторной БД, без локального embedding pipeline.
- Без локальной chat/agent-модели.

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

Для работы с локальными MCP-индексами нужен Online Hybrid (с облачной моделью для
рассуждения) либо отдельный MCP-клиент.

## Почему без embeddings и LanceDB

Точные индексы уже существуют: `bsl-indexer` даёт структурный поиск по коду 1С,
Help Index MCP — FTS5-поиск по справке. Для слабого ноутбука дублирующий векторный
индекс означает дополнительный расход RAM и времени индексации без доказанного
выигрыша в качестве поиска. Векторный слой можно рассмотреть позже и только после
отдельного golden-retrieval сравнения. В текущем профиле его нет.

## Требования и RAM

Ориентир — 16 ГБ RAM. Реальное потребление профиля не измерялось.

`RAM NOT MEASURED`

## Генерация и проверка профилей

Генератор подставляет абсолютные пути вместо шаблонов и пишет детерминированный
UTF-8 (без BOM, LF) в `generated/continue/`. Он не принимает и не печатает API-ключ
и не пишет в пользовательский `~/.continue`.

```powershell
# Online Hybrid
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid

# Offline Lite
.\scripts\28_prepare_continue_profile.ps1 -Profile OfflineLite

# Только проверка (без записи)
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -CheckOnly

# Перезапись существующего файла
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -Force

# Строгая проверка готовности runtime (ненулевой exit, если чего-то нет)
.\scripts\28_prepare_continue_profile.ps1 -Profile OnlineHybrid -RequireRuntimeReady
```

Статический валидатор разбирает YAML и проверяет контракт профилей:

```powershell
python .\scripts\29_validate_continue_profile.py --kind online --config .\generated\continue\online-hybrid.yaml
python .\scripts\29_validate_continue_profile.py --kind offline --config .\generated\continue\offline-lite.yaml
```

## Настройка GROQ_API_KEY

Ключ настраивается поддерживаемым механизмом секретов/переменных окружения Continue
(см. документацию Continue по secrets). В профиле используется только ссылка
`${{ secrets.GROQ_API_KEY }}`.

- Не коммитьте `.env` и любые файлы с реальным ключом.
- Не вставляйте реальное значение ключа в YAML-профиль.
- Генератор никогда не читает и не печатает значение ключа.

## Ollama-модель (вручную)

Автодополнение использует локальную модель. Загрузите её вручную (скрипты профиля
модели не скачивают):

```powershell
ollama pull qwen2.5-coder:1.5b-base
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

- `qwen/qwen3.6-27b` является Preview-моделью. Доступность, rate limits и условия
  free tier могут меняться.
- Профиль не обещает отсутствие KYC, банковской карты, VPN или гарантированную
  работу из конкретной страны.
- Устаревающие Llama 3.1/3.3 не используются как основа профиля (Groq меняет условия
  их доступности на Free/Developer tier).

## Ручной acceptance checklist

Статусы: `PASS` / `FAIL` / `NOT RUN`. Если Continue, ключ Groq или Ollama-модель
отсутствуют, соответствующие проверки — `NOT RUN`, а не `PASS`.

| Проверка | Статус |
| --- | --- |
| Генератор Online Hybrid создаёт валидный YAML без неразрешённых токенов | PASS (pytest) |
| Генератор Offline Lite создаёт валидный YAML | PASS (pytest) |
| Валидатор принимает оба профиля | PASS (pytest) |
| Help MCP readonly: mutating-тулы отсутствуют, SQLite mode=ro, hash/mtime неизменны | PASS (pytest) |
| PRISM eval: точный символ, путь, строка, evidence token | PASS (CI + локально 7/7) |
| PRISM eval: ловушка похожего имени и отсутствующий символ (absence) | PASS (CI + локально 7/7) |
| `.continue/rules/1c-workbench.md` и корневой `.continueignore` существуют | PASS (pytest) |
| BSL example — валидный JSON, диагностика по onSave | PASS (pytest) |
| Continue открыл Online Hybrid и ответил через Groq | NOT RUN (Continue не установлен) |
| Groq-ключ настроен и Agent вызывает MCP | NOT RUN (ключ не задан) |
| Ollama autocomplete работает с `qwen2.5-coder:1.5b-base` | NOT RUN (модель не загружена) |
| BSL Language Server активирован и выдаёт диагностику по onSave | NOT RUN (Java/BSL LS отсутствуют) |
| Измерение RAM под нагрузкой профиля | NOT RUN (`RAM NOT MEASURED`) |
