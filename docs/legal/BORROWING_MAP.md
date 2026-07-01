# Borrowing Map & Legal Notes

> **Дата:** 2026-06-22
> **Цель:** Зафиксировать, что и откуда мы берем (идеи, код, методологию, UX-паттерны), с явной аттрибуцией и legal boundaries.
> **Принцип:** Мы не копируем — мы изучаем, адаптируем, интегрируем с указанием источника.

## 0. Internal planning docs (moved to private repo)

Следующие рабочие документы удалены из публичного репозитория:

- `docs/grant/` (3 файла, 92 KB) — заявка на грант ФСИ "Старт-АИ 2026" и рабочие research notes
- `docs/marketing/` (8 файлов, 145 KB) — черновики community launch, конкурентный анализ, demo video сценарии
- `docs/v1.1/COCKPIT_V0.2_PLAN.md`, `docs/v1.1/PRIVATE_REPO_SPLIT.md` — внутренние планы, выполненные

`docs/v1.1/LINTING_BACKLOG.md` оставлен в публичном репо как `docs/contributing/linting.md` — полезен контрибьюторам.

История файлов сохранена в git log публичного репо (для прозрачности); в `.gitignore` добавлены записи, чтобы предотвратить случайное повторное добавление.

---

## 1. P0 — Интеграция (берём как зависимости с аттрибуцией)

Эти инструменты мы **ставим и используем**. Они — часть toolchain workbench.

| Инструмент | Лицензия | Формат использования | Аттрибуция |
|---|---|---|---|
| **BSL Language Server** | [MIT](https://github.com/1c-syntax/bsl-language-server/blob/master/LICENSE.md) | MCP-обёртка / CLI-вызов для диагностики, explain/fix flows | `1c-syntax/bsl-language-server` |
| **OneScript** | [Apache 2.0](https://github.com/EvilBeaver/OneScript/blob/develop/LICENSE) | Runtime для automation-скриптов, via `oscript` CLI | `EvilBeaver/OneScript` |
| **cc-1c-skills** | [MIT](https://github.com/Nikolay-Shirokov/cc-1c-skills/blob/main/LICENSE) | Подмодуль, навыки для AI-агентов по 1С (уже инициализирован в `tools/cc-1c-skills/`) | `Nikolay-Shirokov/cc-1c-skills` |

**Legal:** Все три — open-source с permissive-лицензиями. MIT и Apache 2.0 разрешают использование, модификацию и распространение при условии указания авторства. Мы указываем авторство:
- В README.md проекта (раздел "Third-Party Components")
- В integration cards каждого инструмента
- В LICENSE файле при распространении

### 1.1 cc-1c-skills — детальная интеграция (Phase A)

**Репозиторий:** `tools/cc-1c-skills/` (подмодуль, MIT)
**Исходник:** [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills)
**Ветка для MCP:** `port-claude-code-py` (Python-скрипты)
**Ветка по умолчанию:** `main` (PowerShell-скрипты)
**Анализ:** `docs/cc-1c-skills-analysis.md`

**Что берём:**
- Логику `*-info` скриптов (Python) — адаптируем под FastMCP-инструменты (read-only)
- Логику `*-validate` скриптов (Python) — адаптируем под quality-gate MCP-инструменты
- SKILL.md как reference для промпт-дизайна и UX-паттернов
- Формат frontmatter (`name`, `description`, `argument-hint`, `allowed-tools`) — как reference для наших skills

**Что НЕ берём (Phase A):**
- PowerShell-скрипты — используем Python-версию для кросс-платформенности MCP
- Write-операции (`*-edit`, `*-compile`, `*-remove`, `*-add`) — откладываем до Phase B (dev-automation)
- Live-режим skills (`db-*`, `web-*`) — откладываем до Phase B (live-1c-bridge)
- Скрипты без Py-реализации (`db-list`, `epf-bsp-*`, `erf-build`, `form-patterns`, `web-test`) — reference-only

**Аттрибуция:**
- `tools/skills-bridge/ATTRIBUTION.md` — ссылка на оригинальный проект
- `tools/skills-bridge/README.md` — "Based on cc-1c-skills by Nikolay-Shirokov (MIT)"
- Комментарии в каждом adapted tool: `# Adapted from cc-1c-skills/scripts/<name>.py (MIT)`
- Integration card: `## Sources` с лицензией и ссылкой
- `docs/cc-1c-skills-analysis.md` — полный каталог с attribution

**Лицензионные границы:**
- MIT разрешает: копировать, модифицировать, распространять с указанием авторства
- Наш MCP-adapter — производная работа, остаётся MIT
- Не удалять LICENSE из `tools/cc-1c-skills/`
- Не выдавать оригинальные skills за свои
- Не копировать текст SKILL.md без пометки (MIT, cc-1c-skills)

**Топ-10 P0 навыков для MCP-обёртки:**
1. `meta-info` — структура объекта метаданных (реквизиты, ТЧ, формы, движения)
2. `form-info` — структура управляемой формы (элементы, реквизиты, команды, события)
3. `skd-info` — структура СКД (наборы, поля, параметры, варианты)
4. `cf-info` — обзор конфигурации (свойства, состав, счётчики)
5. `role-info` — сводка прав роли (объекты, права, RLS)
6. `cfe-diff` — diff расширения с базовой конфигурацией
7. `meta-validate` — валидация объекта метаданных
8. `form-validate` — валидация управляемой формы
9. `subsystem-info` — структура подсистемы (состав, дочерние, интерфейс)
10. `mxl-info` — структура макета MXL (области, параметры, колонки)

---

## 2. P1 — Активная адаптация (берём концепции, НЕ код)

| Инструмент | Лицензия | Что берём | Что НЕ берём |
|---|---|---|---|
| **vanessa-runner** | [Apache 2.0](https://github.com/vanessa-opensource/vanessa-runner) | CI/orchestration workflow, 2.x LTS recipe | Код runner'а — используем как зависимость через `vrunner` |
| **ai-review** | [MIT](https://github.com/Nikita-Filonov/ai-review) | CI-driven AI review workflow model, multi-provider architecture | Код — используем как CLI-инструмент |
| **Vanessa-Automation** | [Apache 2.0](https://github.com/Pr-Mex/vanessa-automation) | Gherkin/BDD как target для AI-генерации тестов | Отложено до появления live mode |
| **YAxUnit** | [Apache 2.0](https://github.com/bia-technologies/yaxunit) | Unit-test структура для quality gate layer | Отложено до появления live mode |
| **1C: Platform Tools** | [MIT](https://github.com/yellow-hammer/vscode-1c-platform-tools) | UX-паттерны: command surface, metadata navigation, test trees, MCP/AI adjacency | Код VSCode extension — не интегрируем |
| **SonarQube BSL Plugin** | [LGPL 3.0](https://github.com/1c-syntax/sonar-bsl-plugin-community) | Quality gate концепция для enterprise-режима | Не встраиваем — документируем как внешний профиль |

**Legal:** Заимствование концепций и UX-паттернов не нарушает авторских прав (идеи не защищены копирайтом, только их выражение). Однако:
- При описании интеграций явно указываем, что это "адаптация подхода из проекта X"
- Не копируем формулировки из README/docs оригинальных проектов — пишем свои
- Не бандлим бинарники

---

## 3. P2 — Методологические заимствования

| Источник | Что берём | Формат |
|---|---|---|
| **Landscape1C** (Oxotka/Landscape1C, MIT) | Структуру карточки: «что это / зачем / с чего начать» | Своя реализация, своя вёрстка, своя специфика |
| **Landscape1C** | Оси навигации: роль, контекст, зрелость, лицензия | Адаптируем под workbench (4 оси: роль, сценарий, зрелость, совместимость) |
| **Landscape1C** | Граф зависимостей между инструментами | Внедряем в Integration Packs как "stack map" |
| **Landscape1C** | Path-based onboarding (Путь) | Operational paths: 10min / 30min / 1day |
| **Landscape1C** | Прозрачная методология разметки | Документируем criteria для supported/experimental/reference-only |
| **Landscape1C** | Expert council model | Для будущей версии — community review board |
| **cc-1c-skills** | Agent Skills формат (skill-based AI workflow) | Адаптируем под opencode/MCP через наш prompt gallery |

**Legal:** Landscape1C — [MIT](https://github.com/Oxotka/Landscape1C?tab=MIT-1-ov-file). Методология, структура данных, оси навигации — идеи, не защищённые копирайтом. Наша реализация:
- Пишем свой текст карточек (не копируем с landscape1c.ru)
- Используем свою цветовую схему и layout
- Не копируем data.js
- Указываем: "UX-модель карточки основана на методологии Landscape1C"
- Даём ссылку на оригинальный проект

---

## 4. Reference-only (изучаем, НЕ берём)

| Инструмент | Причина не брать | Что делаем |
|---|---|---|
| **Confaster** | Закрытый, без репозитория | Изучаем UX, конкурируем |
| **1С:Напарник** | Проприетарный, только EDT | Позиционируемся как альтернатива для opencode/Cursor/любого MCP |
| **Infostart Toolkit** | Условно-бесплатный, закрытый | Reference для understanding рынка |
| **TurboConf** | Проприетарный | Reference |
| **GigaCode (Сбер)** | Закрытый, только GitVerse | Изучаем как тренд |
| **Koda** | Закрытый (pre-release) | Изучаем как тренд |
| **GitHub Copilot / Cursor / Claude Code** | Проприетарные | Изучаем UX, НЕ интегрируем как зависимость |

## 4.1 Proprietary Optional CLI

| Инструмент | Статус | Что делаем | Граница |
|---|---|---|---|
| **ibcmd** | Закрытый binary от 1С, устанавливается с платформой | MCP-обёртка вызывает локально установленный CLI для export/import сценариев Phase B | Не бандлим, не копируем документацию, write-команды gated и выключены по умолчанию |

---

## 5. Legal Boundaries — чёткие правила

### МОЖНО
- ✅ Использовать open-source проекты согласно их лицензиям (MIT, Apache 2.0, LGPL)
- ✅ Указывать проекты как источники вдохновения
- ✅ Адаптировать архитектурные концепции (MCP, LSP, skill-based workflows)
- ✅ Использовать стандартные форматы (MCP JSON-RPC, Markdown, JSON)
- ✅ Писать свои формулировки, опираясь на функциональность, а не на чужой текст
- ✅ Приводить цитаты из docs с указанием источника (как reference)
- ✅ Форкать MIT-проекты с сохранением LICENSE

### НЕЛЬЗЯ
- ❌ Копировать текст карточек с landscape1c.ru (даже с пересказом)
- ❌ Копировать data.js структуру один-в-один
- ❌ Бандлить закрытые бинарники
- ❌ Использовать код с несовместимыми лицензиями (GPL в коммерческом closed-source)
- ❌ Удалять LICENSE/ATTRIBUTION из open-source зависимостей
- ❌ Выдавать чужие проекты за свои ("мы сделали BSL LS" — нет)
- ❌ Претендовать на совместимость, не протестировав её
- ❌ Использовать trademarked names без разрешения (1С is trademark of 1С Company)

### Аттрибуция в коде
Каждый integration card содержит:
```markdown
## Sources
- Original project: [name](url)
- License: [type](url)
- Adaptation for 1c-ai-workbench: [our notes]
```

### Аттрибуция в README
```markdown
## Third-Party Components

1c-ai-workbench integrates or references these open-source projects:

| Project | License | Usage |
|---|---|---|
| BSL Language Server (1c-syntax) | MIT | Static analysis engine |
| OneScript (EvilBeaver) | Apache 2.0 | Automation runtime |
| cc-1c-skills (Nikolay-Shirokov) | MIT | 1C-specific AI agent skills |
| vanessa-runner | Apache 2.0 | CI test orchestration |
| ai-review (Nikita-Filonov) | MIT | AI code review workflow model |
| Landscape1C (Oxotka) | MIT | Integration card methodology |
```

---

## 6. Что НЕ требует заимствования (уже есть в проекте)

Проверка: следующие элементы УЖЕ реализованы в 1c-ai-workbench, их не нужно "брать" извне:

| Элемент | Где |
|---|---|
| Индексация 1C выгрузки | `bsl-indexer` (Rust) из `code-index-mcp` |
| MCP сервер | `opencode.jsonc` + `bsl-indexer.exe serve` |
| Healthcheck | `06_healthcheck.ps1` |
| Risk scan (10 правил) | `10_risk_scan.ps1` |
| Explain module | `11_explain_module.ps1` |
| Prompt gallery (15 prompts) | `prompts/*.md` |
| AI Rules (7 path-scoped) | `rules/*.md` |
| Integration packs (5 packs, 10 tools) | `configs/integration-packs.json` |
| Integration cards (7 cards) | `docs/phase-a/integration-cards/*.md` |
| Check scripts for packs | `13_check_bsl_quality_pack.ps1`, `14_check_testing_pack.ps1`, `15_check_review_pack.ps1` |
| Demo showcase | `demo-showcase/*` |

---

## 7. Gap analysis: что нужно ДЕЙСТВИТЕЛЬНО построить

После инвентаризации — вот что НУЖНО сделать (этого нет ни в одном внешнем проекте):

| Фича | Почему нет готового решения |
|---|---|
| **MCP-инструмент "prompt router"** | Никто не делал MCP-обёртку для 1C prompt gallery |
| **BSL LS diagnostics → risk scan bridge** | Нужно соединить вывод BSL LS с нашей risk-системой |
| **Semantic search (RAG) для 1C кода** | Никто в 1C-экосистеме не делает векторный поиск по выгрузке |
| **Live mode через ibcmd** | ibcmd есть, но никто не оборачивал его в MCP для AI-агентов |
| **Role-based entry points** | Наша собственная фича для персонализации |
| **Multi-config management** | Наша архитектурная задача |
| **cc-1c-skills bridge** | Связать 70+ готовых Claude Code skills с нашим MCP |

Это НЕ заимствования — это наша добавленная стоимость.

---

## 8. Чеклист перед коммитом/релизом

- [ ] Все integration cards содержат `## Sources` с лицензией
- [ ] README содержит `## Third-Party Components` секцию
- [ ] LICENSE файлы зависимостей не удалены
- [ ] Нет скопированного текста из landscape1c.ru или чужих README
- [ ] Нет closed-source бинарников в репозитории
- [ ] Все ссылки на оригинальные проекты работают
- [ ] Аттрибуция добавлена для каждого заимствованного паттерна
