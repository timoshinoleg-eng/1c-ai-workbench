# cc-1c-skills: Полный анализ и план интеграции в 1c-ai-workbench

> **Дата:** 2026-07-22
> **Источник:** `tools/cc-1c-skills/` (подмодуль, MIT, Nikolay-Shirokov)
> **Ветка:** `main` (PowerShell-скрипты), `port-claude-code-py` (Python-скрипты)
> **Цель:** Фаза 1 — инвентаризация, анализ пересечения, определение P0, план внедрения

---

## 1. Полный каталог навыков (68 skills)

### 1.1 Сводка по доменам

| Домен | Количество | Тип операций |
|-------|-----------|--------------|
| **cf** | 4 | Конфигурация (создание, редактирование, анализ, валидация) |
| **cfe** | 5 | Расширения конфигурации (CFE) — создание, заимствование, diff, патчи, валидация |
| **db** | 9 | Операции с ИБ (создание, выгрузка, загрузка, запуск, обновление) — **требуют live 1С** |
| **epf** | 6 | Внешние обработки (scaffold, сборка, разбор, БСП, валидация) |
| **erf** | 4 | Внешние отчёты (scaffold, сборка, разбор, валидация) |
| **form** | 8 | Управляемые формы (создание, компиляция, декомпиляция, редактирование, анализ, валидация, паттерны) |
| **help** | 1 | Встроенная справка (добавление) |
| **img** | 1 | Изображения (сетка для анализа макетов) |
| **interface** | 2 | Командный интерфейс (редактирование, валидация) |
| **meta** | 5 | Объекты метаданных (создание, редактирование, анализ, удаление, валидация) |
| **mxl** | 4 | Табличные документы / макеты (компиляция, декомпиляция, анализ, валидация) |
| **role** | 3 | Роли (создание, анализ, валидация) |
| **skd** | 5 | СКД / отчёты (компиляция, декомпиляция, редактирование, анализ, валидация) |
| **subsystem** | 4 | Подсистемы (создание, редактирование, анализ, валидация) |
| **template** | 2 | Макеты (добавление, удаление) |
| **web** | 5 | Веб-публикации (инфо, публикация, остановка, тест, удаление) — **требуют live Apache + 1С** |

**Итого:** 68 навыков, из которых:
- **42** имеют Python-скрипты (готовы для Python MCP-обёртки)
- **43** имеют PowerShell-скрипты
- **10** имеют только SKILL.md (без скриптов: `db-list`, `epf-bsp-*`, `erf-build/dump/validate`, `form-patterns`, `web-test`)

### 1.2 Полная таблица: имя → описание → pack → приоритет

| # | Навык | Описание | Pack | Приоритет | PS | Py |
|---|-------|----------|------|-----------|----|----|
| 1 | `cf-edit` | Точечное редактирование конфигурации 1С | — | **P1** (write) | ✅ | ✅ |
| 2 | `cf-info` | Анализ структуры конфигурации 1С — свойства, состав, счётчики | `bsl-quality` | **P0** | ✅ | ✅ |
| 3 | `cf-init` | Создать пустую конфигурацию 1С (scaffold XML) | — | **P1** (write) | ✅ | ✅ |
| 4 | `cf-validate` | Валидация конфигурации 1С | `bsl-quality` | **P0** | ✅ | ✅ |
| 5 | `cfe-borrow` | Заимствование объектов из конфигурации в расширение | — | **P1** (write) | ✅ | ✅ |
| 6 | `cfe-diff` | Анализ расширения — состав, заимствования, перехватчики | `review` | **P0** | ✅ | ✅ |
| 7 | `cfe-init` | Создать расширение конфигурации 1С (CFE) | — | **P1** (write) | ✅ | ✅ |
| 8 | `cfe-patch-method` | Генерация перехватчика метода в расширении | — | **P1** (write) | ✅ | ✅ |
| 9 | `cfe-validate` | Валидация расширения конфигурации 1С | `bsl-quality` | **P0** | ✅ | ✅ |
| 10 | `db-create` | Создание информационной базы 1С | `testing` | **P1** (live) | ✅ | ✅ |
| 11 | `db-dump-cf` | Выгрузка конфигурации 1С в CF-файл | `testing` | **P1** (live) | ✅ | ✅ |
| 12 | `db-dump-xml` | Выгрузка конфигурации 1С в XML-файлы | `testing` | **P1** (live) | ✅ | ✅ |
| 13 | `db-list` | Управление реестром баз данных 1С (.v8-project.json) | `testing` | **P2** (no scripts) | ❌ | ❌ |
| 14 | `db-load-cf` | Загрузка конфигурации 1С из CF-файла | `testing` | **P1** (live) | ✅ | ✅ |
| 15 | `db-load-git` | Загрузка изменений из Git в базу 1С | `testing` | **P1** (live) | ✅ | ✅ |
| 16 | `db-load-xml` | Загрузка конфигурации 1С из XML-файлов | `testing` | **P1** (live) | ✅ | ✅ |
| 17 | `db-run` | Запуск 1С:Предприятие | `testing` | **P1** (live) | ✅ | ✅ |
| 18 | `db-update` | Обновление конфигурации базы данных 1С | `testing` | **P1** (live) | ✅ | ✅ |
| 19 | `epf-bsp-add-command` | Определить команду в БСП-описании обработки | `reference` | **P2** (no scripts) | ❌ | ❌ |
| 20 | `epf-bsp-init` | Сформировать функцию `СведенияОВнешнейОбработке` | `reference` | **P2** (no scripts) | ❌ | ❌ |
| 21 | `epf-build` | Собрать внешнюю обработку 1С (EPF) из XML-исходников | — | **P1** (write) | ✅ | ✅ |
| 22 | `epf-dump` | Разобрать EPF-файл в XML-исходники | — | **P1** (write) | ✅ | ✅ |
| 23 | `epf-init` | Создать пустую внешнюю обработку 1С | — | **P1** (write) | ✅ | ✅ |
| 24 | `epf-validate` | Валидация внешней обработки 1С | `bsl-quality` | **P0** | ✅ | ✅ |
| 25 | `erf-build` | Собрать внешний отчёт 1С (ERF) из XML-исходников | — | **P1** (write) | ❌ | ❌ |
| 26 | `erf-dump` | Разобрать ERF-файл отчёта в XML-исходники | — | **P1** (write) | ❌ | ❌ |
| 27 | `erf-init` | Создать пустой внешний отчёт 1С | — | **P1** (write) | ✅ | ✅ |
| 28 | `erf-validate` | Валидация внешнего отчёта 1С | `bsl-quality` | **P0** | ❌ | ❌ |
| 29 | `form-add` | Добавить пустую управляемую форму к объекту 1С | — | **P1** (write) | ✅ | ✅ |
| 30 | `form-compile` | Компиляция управляемой формы из JSON-определения | — | **P1** (write) | ✅ | ✅ |
| 31 | `form-decompile` | Декомпиляция управляемой формы в JSON-черновик | — | **P1** (write) | ✅ | ✅ |
| 32 | `form-edit` | Добавление элементов, реквизитов и команд в форму | — | **P1** (write) | ✅ | ✅ |
| 33 | `form-info` | Анализ структуры управляемой формы — элементы, реквизиты, команды | `vscode` | **P0** | ✅ | ✅ |
| 34 | `form-patterns` | Справочник паттернов компоновки управляемых форм | `reference` | **P2** (no scripts) | ❌ | ❌ |
| 35 | `form-remove` | Удалить форму из объекта 1С | — | **P1** (write) | ✅ | ✅ |
| 36 | `form-validate` | Валидация управляемой формы | `bsl-quality` | **P0** | ✅ | ✅ |
| 37 | `help-add` | Добавить встроенную справку к объекту 1С | — | **P1** (write) | ✅ | ✅ |
| 38 | `img-grid` | Наложить пронумерованную сетку на изображение | `reference` | **P2** ( niche) | ❌ | ✅ |
| 39 | `interface-edit` | Настройка командного интерфейса подсистемы | — | **P1** (write) | ✅ | ✅ |
| 40 | `interface-validate` | Валидация командного интерфейса | `bsl-quality` | **P0** | ✅ | ✅ |
| 41 | `meta-compile` | Создать объект метаданных 1С из JSON | — | **P1** (write) | ✅ | ✅ |
| 42 | `meta-edit` | Точечное редактирование объекта метаданных | — | **P1** (write) | ✅ | ✅ |
| 43 | `meta-info` | Анализ структуры объекта метаданных — реквизиты, ТЧ, формы, движения | `vscode` | **P0** | ✅ | ✅ |
| 44 | `meta-remove` | Удалить объект метаданных из конфигурации | — | **P1** (write) | ✅ | ✅ |
| 45 | `meta-validate` | Валидация объекта метаданных | `bsl-quality` | **P0** | ✅ | ✅ |
| 46 | `mxl-compile` | Компиляция табличного документа (MXL) из JSON | — | **P1** (write) | ✅ | ✅ |
| 47 | `mxl-decompile` | Декомпиляция MXL в JSON | — | **P1** (write) | ✅ | ✅ |
| 48 | `mxl-info` | Анализ структуры макета MXL — области, параметры, колонки | `vscode` | **P0** | ✅ | ✅ |
| 49 | `mxl-validate` | Валидация макета MXL | `bsl-quality` | **P0** | ✅ | ✅ |
| 50 | `role-compile` | Создание роли 1С из описания прав | — | **P1** (write) | ✅ | ✅ |
| 51 | `role-info` | Компактная сводка прав роли — объекты, права, RLS | `vscode` | **P0** | ✅ | ✅ |
| 52 | `role-validate` | Валидация роли 1С | `bsl-quality` | **P0** | ✅ | ✅ |
| 53 | `skd-compile` | Компиляция СКД из JSON-определения | — | **P1** (write) | ✅ | ✅ |
| 54 | `skd-decompile` | Декомпиляция СКД в JSON-черновик | — | **P1** (write) | ✅ | ✅ |
| 55 | `skd-edit` | Точечное редактирование СКД | — | **P1** (write) | ✅ | ✅ |
| 56 | `skd-info` | Анализ структуры СКД — наборы, поля, параметры, варианты | `vscode` | **P0** | ✅ | ✅ |
| 57 | `skd-validate` | Валидация схемы компоновки данных | `bsl-quality` | **P0** | ✅ | ✅ |
| 58 | `subsystem-compile` | Создать подсистему 1С из JSON | — | **P1** (write) | ✅ | ✅ |
| 59 | `subsystem-edit` | Точечное редактирование подсистемы | — | **P1** (write) | ✅ | ✅ |
| 60 | `subsystem-info` | Анализ структуры подсистемы — состав, дочерние, интерфейс | `vscode` | **P0** | ✅ | ✅ |
| 61 | `subsystem-validate` | Валидация подсистемы | `bsl-quality` | **P0** | ✅ | ✅ |
| 62 | `template-add` | Добавить пустой макет к объекту | — | **P1** (write) | ✅ | ✅ |
| 63 | `template-remove` | Удалить макет из объекта | — | **P1** (write) | ✅ | ✅ |
| 64 | `web-info` | Статус Apache и веб-публикаций 1С | `testing` | **P1** (live) | ✅ | ✅ |
| 65 | `web-publish` | Публикация ИБ через Apache | `testing` | **P1** (live) | ✅ | ✅ |
| 66 | `web-stop` | Остановка Apache HTTP Server | `testing` | **P1** (live) | ✅ | ✅ |
| 67 | `web-test` | Тестирование 1С через веб-клиент (браузер) | `testing` | **P2** (no scripts) | ❌ | ❌ |
| 68 | `web-unpublish` | Удаление веб-публикации из Apache | `testing` | **P1** (live) | ✅ | ✅ |

---

## 2. Анализ пересечения с существующими промптами (17 prompts)

### 2.1 Существующие промпты (prompts/*.md)

| # | Промпт | Описание | Категория |
|---|--------|----------|-----------|
| 1 | `/analyze-query` | Анализ текста запроса 1С — извлечение объектов, таблиц, JOIN | Анализ кода |
| 2 | `/audit-metadata` | Аудит метаданных — неиспользуемые объекты, дубли, нейминг | Анализ метаданных |
| 3 | `/compare-versions` | Сравнение двух версий конфигурации | Анализ метаданных |
| 4 | `/debug-print` | Добавление отладочной печати в BSL | Кодогенерация |
| 5 | `/docgen` | Генерация документации по модулю/объекту | Документация |
| 6 | `/explain-module` | Объяснение модуля — evidence-first summary | Анализ кода |
| 7 | `/find-by-pattern` | Поиск по regex-паттерну в телах функций | Поиск |
| 8 | `/find-object` | Поиск использования объекта метаданных в коде | Поиск |
| 9 | `/find-similar` | Поиск похожих реализаций | Поиск |
| 10 | `/onboard` | Онбординг нового разработчика — карта конфигурации | Документация |
| 11 | `/plan-refactor` | План рефакторинга — граф зависимостей | Анализ кода |
| 12 | `/query-optimizer` | Оптимизация текста запроса 1С | Анализ кода |
| 13 | `/review-bsl` | Ревью BSL-кода по эвристикам | Анализ кода |
| 14 | `/risk-scan` | Сканирование рисков конфигурации | Анализ кода |
| 15 | `/architecture-decide` | Архитектурное решение | Методология |
| 16 | `/integrate-tool` | Интеграция инструмента | Методология |
| 17 | `/trace-flow` | Трассировка потока выполнения | Анализ кода |

### 2.2 Карта пересечений

**Ключевое открытие:** cc-1c-skills и существующие prompts — **практически не пересекаются**. Они решают разные задачи на разных уровнях абстракции:

- **Наши prompts** — это **AI-аналитика** (поиск, ревью, объяснение, оптимизация) — работают на **read-only dump** через code-index-mcp.
- **cc-1c-skills** — это **1C-разработка** (создание объектов, редактирование метаданных, сборка EPF, валидация) — работают на **XML-исходниках** через PowerShell/Python скрипты.

#### Таблица пересечения: навык × промпт

| Навык | Промпт | Тип пересечения | Комментарий |
|-------|--------|-----------------|-------------|
| `audit-metadata` | `/audit-metadata` | **Функциональное пересечение** (частичное) | Оба анализируют метаданные, но cc-1c-skills `meta-info` — это **структурный анализ** (реквизиты, ТЧ), а наш `/audit-metadata` — **эвристический аудит** (неиспользуемые, дубли). Не дублируются, можно дополнить. |
| `cf-info` | `/onboard` | **Функциональное пересечение** (частичное) | `cf-info` даёт структуру конфигурации; `/onboard` использует repo-map. Можно усилить `/onboard` данными `cf-info`. |
| `meta-validate` | `/risk-scan` | **Функциональное пересечение** (частичное) | `meta-validate` проверяет **корректность XML/метаданных** (структурная валидация), `/risk-scan` — **эвристики кода** (запрос в цикле, вложенность). Разные уровни. |
| `form-info` | `/explain-module` | **Нет прямого пересечения** | `form-info` анализирует **XML-структуру формы**, `/explain-module` — **BSL-код модуля**. Комплементарны. |
| `role-info` | `/find-object` | **Нет пересечения** | `role-info` — анализ прав; `/find-object` — поиск использования. |
| `cfe-diff` | `/compare-versions` | **Функциональное пересечение** (частичное) | `cfe-diff` сравнивает **расширение с базой**; `/compare-versions` — **два дампа**. Похожая задача, разные объекты. |
| `skd-info` | `/analyze-query` | **Нет пересечения** | `skd-info` — структура СКД; `/analyze-query` — текст запроса BSL. Комплементарны. |
| `mxl-info` | `/docgen` | **Нет пересечения** | `mxl-info` — структура макета; `/docgen` — документация модуля. |

#### Результат gap-анализа

| Тип | Навыки / Промпты | Вывод |
|-----|-----------------|-------|
| **Прямое совпадение** | Нет | Ни один skill.name не совпадает с prompt.name по сути |
| **Функциональное пересечение** | `meta-info` ↔ `/audit-metadata`, `cf-info` ↔ `/onboard`, `cfe-diff` ↔ `/compare-versions` | Частичное — можно усилить промпты данными skills, но не заменить |
| **Нет аналога (gap)** | **16 навыков** — всё семейство `*-info`, `*-validate`, `cfe-diff`, `form-patterns`, `img-grid` | cc-1c-skills заполняет огромный gap: **структурный анализ метаданных и валидация XML-исходников** — то, чего нет в наших промптах |
| **Объединить** | Не требуется | Навыки и промпты работают на разных уровнях; объединение не даст синергии |

### 2.3 Вывод по пересечению

> **cc-1c-skills не дублирует существующие промпты. Они добавляют новый слой: «интроспекция и валидация метаданных 1С».**
>
> Наши промпты — это «что происходит в коде».
> cc-1c-skills — это «из чего состоит конфигурация и корректна ли её структура».
>
> Это комплементарные, а не конкурирующие наборы инструментов.

---

## 3. Топ-10 навыков для P0 (внедрение в workbench)

### 3.1 Критерии отбора P0

1. ✅ Работает на **read-only** данных (XML-выгрузка в `source-mirror/`)
2. ✅ **Не требует** live-режима 1С или Apache
3. ✅ Можно обернуть в **MCP-инструмент за 1 день**
4. ✅ Покрывает **gap** в существующих промптах
5. ✅ **MIT-совместим** — копируем с attribution
6. ✅ Имеет **Python-скрипт** (готов для FastMCP-обёртки)

### 3.2 Ранжированный список топ-10

| # | Навык | Зачем | Pack | Почему P0 |
|---|-------|-------|------|-----------|
| **1** | `meta-info` | Анализ структуры объекта метаданных — реквизиты, ТЧ, формы, движения, типы | `vscode` | **Ключевой gap.** Наши промпты не умеют «раскрыть» объект метаданных. MCP-инструмент вернёт структуру любого справочника/документа/регистра. Read-only, Py-скрипт есть. |
| **2** | `form-info` | Анализ структуры управляемой формы — элементы, реквизиты, команды, события | `vscode` | **Ключевой gap.** Промпты анализируют BSL-модули форм, но не её XML-структуру. Полезно для рефакторинга и аудита. Read-only, Py-скрипт есть. |
| **3** | `skd-info` | Анализ СКД — наборы данных, поля, параметры, варианты, связи | `vscode` | **Ключевой gap.** Отчёты 1С — чёрный ящик для AI. `skd-info` открывает структуру СКД для анализа. Read-only, Py-скрипт есть. |
| **4** | `cf-info` | Анализ конфигурации — свойства, состав, счётчики объектов | `bsl-quality` | **Обзорная ценность.** Даёт «высоту птичьего полёта» над конфигурацией. Комплементарен `/onboard`. Read-only, Py-скрипт есть. |
| **5** | `role-info` | Сводка прав роли — объекты, права, RLS, шаблоны | `review` | **Security-аудит.** Наши промпты не покрывают анализ прав доступа. Критично для аудита и ревью. Read-only, Py-скрипт есть. |
| **6** | `cfe-diff` | Diff расширения с базовой конфигурацией | `review` | **Code review для CFE.** Уникальная функция: показывает что заимствовано, что перехвачено, что изменено. Read-only, Py-скрипт есть. |
| **7** | `meta-validate` | Валидация объекта метаданных | `bsl-quality` | **Quality gate.** Проверяет корректность XML-структуры объекта. Можно добавить в CI-проверки. Read-only, Py-скрипт есть. |
| **8** | `form-validate` | Валидация управляемой формы | `bsl-quality` | **Quality gate.** Проверяет корректность Form.xml. Можно добавить в CI-проверки. Read-only, Py-скрипт есть. |
| **9** | `subsystem-info` | Анализ подсистемы — состав, дочерние, командный интерфейс | `vscode` | **Навигация.** Показывает иерархию подсистем и их содержимое. Полезно для onboarding. Read-only, Py-скрипт есть. |
| **10** | `mxl-info` | Анализ макета MXL — области, параметры, колонки | `vscode` | **Печатные формы.** Раскрывает структуру макетов печатных форм. Read-only, Py-скрипт есть. |

### 3.3 P1 — навыки для live-режима (отложить до Phase B)

| Навык | Почему P1 | Когда понадобится |
|-------|-----------|-----------------|
| `db-dump-xml` | Требует `1cv8.exe` для выгрузки | Phase B: live-1c-bridge |
| `db-load-xml` | Требует `1cv8.exe` для загрузки | Phase B: live-1c-bridge |
| `db-run` | Требует запущенную 1С | Phase B: live-1c-bridge |
| `db-update` | Требует `1cv8.exe` | Phase B: live-1c-bridge |
| `web-info` | Требует Apache + 1С | Phase B: web-dev pack |
| `web-publish` | Требует Apache + 1С | Phase B: web-dev pack |
| `epf-build` | Требует `1cv8.exe` для сборки EPF | Phase B: live-1c-bridge |
| `cf-edit` | Write-операция | Phase B: dev-automation |
| `meta-edit` | Write-операция | Phase B: dev-automation |
| `form-edit` | Write-операция | Phase B: dev-automation |

### 3.4 P2 — нишевые / reference

| Навык | Почему P2 |
|-------|-----------|
| `db-list` | Нет скриптов; проще сделать свой JSON-редактор |
| `epf-bsp-add-command` | Нет скриптов; БСП-специфично |
| `epf-bsp-init` | Нет скриптов; БСП-специфично |
| `erf-build/dump/validate` | Нет скриптов; erf-архетип редко нужен отдельно от epf |
| `form-patterns` | Нет скриптов; справочник, можно вынести в rules |
| `web-test` | Нет скриптов; требует браузерной автоматизации |
| `img-grid` | Нишевый (анализ скриншотов); Py есть, но слабо связан с 1C |

---

## 4. План внедрения (4 фазы)

### 4.1 Фаза 1 — инвентаризация ✅ (1 день) — **ВЫПОЛНЕНО**

- [x] Полный каталог 68 навыков (таблица в разделе 1)
- [x] Анализ пересечения с 17 промптами (раздел 2)
- [x] Определение топ-10 для P0 (раздел 3)
- [x] Обновление BORROWING_MAP.md с разделом cc-1c-skills (см. раздел 6)

**Документ:** `docs/cc-1c-skills-analysis.md` (этот файл)

---

### 4.2 Фаза 2 — MCP-обёртка (2–3 дня)

#### Шаг 2.1: Выбор 3 пилотных навыка

Рекомендуемый пилот (минимальный набор для первого MCP-сервера):

1. **`meta-info`** — самый универсальный инструмент (анализ любого объекта метаданных)
2. **`form-info`** — формы — самый частый объект вопросов разработчиков
3. **`skd-info`** — СКД — самый сложный для понимания без инструментария

#### Шаг 2.2: Создание `tools/skills-bridge/`

```
tools/skills-bridge/
├── server.py              # FastMCP entry point
├── requirements.txt       # fastmcp, lxml, httpx
├── README.md              # описание + attribution
├── ATTRIBUTION.md         # ссылка на cc-1c-skills
├── LICENSE                # MIT (как у оригинала)
└── tools/
    ├── __init__.py
    ├── meta_info.py       # адаптация scripts/meta-info.py
    ├── form_info.py       # адаптация scripts/form-info.py
    └── skd_info.py        # адаптация scripts/skd-info.py
```

**Архитектура `server.py`:**

```python
from fastmcp import FastMCP
from pathlib import Path
from tools.meta_info import analyze_meta
from tools.form_info import analyze_form
from tools.skd_info import analyze_skd

mcp = FastMCP(
    "1c-skills",
    description="1C:Enterprise development skills bridge — read-only metadata introspection"
)

SOURCE_MIRROR = Path("C:/1c-ai-workbench/generated/extract")

@mcp.tool()
async def meta_info(object_path: str, mode: str = "full") -> str:
    """
    Анализ структуры объекта метаданных 1С (реквизиты, ТЧ, формы, движения).

    Args:
        object_path: Относительный путь к объекту (например, "Catalogs/Товары")
        mode: "overview" | "brief" | "full"

    Returns:
        Markdown-структура объекта с реквизитами, табличными частями, формами.
    """
    abs_path = SOURCE_MIRROR / object_path
    if not abs_path.exists():
        return f"❌ Объект не найден: {abs_path}"
    return analyze_meta(abs_path, mode)

@mcp.tool()
async def form_info(form_path: str) -> str:
    """
    Анализ структуры управляемой формы 1С (элементы, реквизиты, команды, события).

    Args:
        form_path: Относительный путь к Form.xml (например, "Documents/Реализация/Forms/ФормаДокумента/Ext/Form.xml")

    Returns:
        Markdown-структура формы.
    """
    abs_path = SOURCE_MIRROR / form_path
    if not abs_path.exists():
        return f"❌ Форма не найдена: {abs_path}"
    return analyze_form(abs_path)

@mcp.tool()
async def skd_info(template_path: str, mode: str = "overview") -> str:
    """
    Анализ схемы компоновки данных (СКД) — наборы, поля, параметры, варианты.

    Args:
        template_path: Путь к Template.xml с СКД
        mode: "overview" | "query" | "fields" | "links" | "calculated"

    Returns:
        Markdown-структура СКД.
    """
    abs_path = SOURCE_MIRROR / template_path
    if not abs_path.exists():
        return f"❌ Шаблон СКД не найден: {abs_path}"
    return analyze_skd(abs_path, mode)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

**Ключевое решение:** каждый инструмент адаптирует **логику** оригинального `scripts/<skill>.py` из cc-1c-skills (MIT позволяет), но переписывает **интерфейс** под FastMCP. Аттрибуция: `ATTRIBUTION.md` + комментарии в коде.

#### Шаг 2.3: Регистрация в `opencode.jsonc`

```jsonc
{
  "mcpServers": {
    "code-index": {
      "type": "stdio",
      "command": "C:\\1c-ai-workbench\\tools\\code-index-mcp\\target\\release\\bsl-indexer.exe",
      "args": ["serve", "--path", "main=C:\\1c-ai-workbench\\generated\\extract"]
    },
    "skills-bridge": {
      "type": "stdio",
      "command": "python",
      "args": [
        "-m", "uvicorn",
        "tools.skills-bridge.server:mcp",
        "--port", "8433"
      ]
    }
  }
}
```

> **Важно:** для stdio-MCP рекомендуется запускать `server.py` напрямую:
> ```jsonc
> "skills-bridge": {
>   "type": "stdio",
>   "command": "python",
>   "args": ["C:\\1c-ai-workbench\\tools\\skills-bridge\\server.py"]
> }
> ```

#### Шаг 2.4: Check-скрипт

Создать `scripts/16_check_skills_bridge.ps1`:

```powershell
param([switch]$Fix)

Write-Host "=== Skills Bridge Pack ===" -ForegroundColor Cyan

$pythonOk = $false
try {
    $v = python --version 2>&1
    Write-Host "  [OK] Python: $v" -ForegroundColor Green
    $pythonOk = $true
} catch {
    Write-Host "  [FAIL] Python not found" -ForegroundColor Red
}

$depsOk = $false
if ($pythonOk) {
    try {
        python -c "from fastmcp import FastMCP; import lxml; import httpx; print('OK')" 2>$null
        Write-Host "  [OK] Dependencies (fastmcp, lxml, httpx)" -ForegroundColor Green
        $depsOk = $true
    } catch {
        Write-Host "  [FAIL] Missing dependencies" -ForegroundColor Red
    }
}

$bridgeOk = $false
if ($depsOk) {
    try {
        $env:PYTHONPATH = "C:\1c-ai-workbench\tools\skills-bridge"
        $tools = python -c "import sys; sys.path.insert(0, 'C:\\1c-ai-workbench\\tools\\skills-bridge'); from server import mcp; print(len(mcp._tools))" 2>$null
        Write-Host "  [OK] Skills bridge loads ($tools tools)" -ForegroundColor Green
        $bridgeOk = $true
    } catch {
        Write-Host "  [FAIL] Skills bridge error: $_" -ForegroundColor Red
    }
}

if (-not $bridgeOk -and $Fix) {
    Write-Host "Fixing..." -ForegroundColor Yellow
    pip install fastmcp lxml httpx
}

$bridgeOk
```

---

### 4.3 Фаза 3 — встройка в integration packs (1 день)

#### Шаг 3.1: Привязка навыков к integration packs

Обновить `configs/integration-packs.json` — добавить новый инструмент `skills-bridge` в каждый pack, где он уместен:

```json
{
  "id": "skills-bridge",
  "name": "Skills Bridge (cc-1c-skills)",
  "pack": "vscode",
  "status": "experimental",
  "why": "MCP-обёртка для 70+ Claude Code skills от Nikolay-Shirokov. Добавляет интроспекцию метаданных 1С (объекты, формы, СКД, роли, подсистемы) и валидацию XML-структур.",
  "smoke_check": {
    "type": "command",
    "command": "python C:\\1c-ai-workbench\\tools\\skills-bridge\\server.py --help",
    "expected": "FastMCP help or server start message"
  },
  "next_scenario": "Run meta-info on a catalog object, then form-info on its form, then skd-info on a report template.",
  "sources": [
    "https://github.com/Nikolay-Shirokov/cc-1c-skills",
    "https://github.com/Nikolay-Shirokov/cc-1c-skills/blob/main/LICENSE"
  ]
}
```

#### Шаг 3.2: Integration card

Создать `docs/phase-a/integration-cards/skills-bridge.md`:

```markdown
# Integration Card: Skills Bridge

**Статус:** experimental
**Pack:** VS Code Cockpit / BSL Quality / Review
**Лицензия:** MIT
**Источник:** [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) by Nikolay-Shirokov
**Наш адаптер:** `tools/skills-bridge/` — MCP-обёртка на FastMCP

## Что делает

Предоставляет AI-агенту 10+ инструментов для read-only интроспекции метаданных 1С:

- `meta_info` — структура объекта (реквизиты, ТЧ, формы, движения)
- `form_info` — структура управляемой формы (элементы, реквизиты, команды)
- `skd_info` — структура СКД (наборы, поля, параметры, варианты)
- `role_info` — права роли (объекты, RLS)
- `subsystem_info` — состав подсистемы
- `cf_info` — обзор конфигурации
- `cfe_diff` — diff расширения с базой
- `meta_validate`, `form_validate`, `skd_validate`, `role_validate` — валидация XML

## Зависимости

- Python 3.10+
- `pip install fastmcp lxml httpx`
- source-mirror (XML-выгрузка в `generated/extract/`)

## Как включить

1. `pip install fastmcp lxml httpx`
2. Добавить `skills-bridge` в `opencode.jsonc` mcpServers
3. `python tools/skills-bridge/server.py` — тестовый запуск
4. `scripts/16_check_skills_bridge.ps1` — проверка

## Sources

- Original project: [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) (MIT)
- Our adaptation: MCP-wrapper with FastMCP, read-only, source-mirror based
```

#### Шаг 3.3: Обновление install profiles

Обновить `configs/install-profiles.json`:

- **Developer:** добавить шаг `skills_bridge` после `explain_module` (позволяет разработчику «раскрыть» объект перед рефакторингом)
- **Partner:** добавить шаг `skills_bridge` в лёгком режиме (только `meta_info` + `cf_info` — базовый обзор)
- **Advanced AI:** добавить шаг `skills_bridge` после `prompt_gallery` (расширяет Prompt Gallery инструментами)

```json
{
  "id": "developer",
  "title": "Developer",
  "goal": "Prepare code navigation, risk scan, explain-module, and metadata introspection workflows.",
  "steps": ["ensure_indexer", "index_dump", "healthcheck", "risk_scan", "explain_module", "skills_bridge"],
  "recommended_for": ["1C developer", "tech lead", "refactoring audit"]
}
```

---

### 4.4 Фаза 4 — валидация (0.5 дня)

- [ ] **Smoke test:** каждый инструмент возвращает результат на demo-конфигурации
- [ ] **Проверка visibility:** `opencode tool list` показывает `meta_info`, `form_info`, `skd_info`
- [ ] **Проверка изоляции:** skills-bridge не ломает code-index-mcp (проверить параллельный запуск)
- [ ] **Partner install:** чистая установка с нуля — `scripts/16_check_skills_bridge.ps1` проходит
- [ ] **Аттрибуция:** `ATTRIBUTION.md` и `README.md` содержат ссылку на Nikolay-Shirokov

---

## 5. Техническая архитектура (итоговая)

```
┌────────────────────────────────────────────────────────────┐
│                   AI Agent                                 │
│         (opencode / Cursor / Claude Code)                  │
└─────┬───────────────────────────────────┬──────────────────┘
      │ MCP call                          │ MCP call
┌─────▼──────────┐              ┌─────────▼──────────┐
│  code-index-   │              │    skills-bridge    │
│  mcp           │              │    (FastMCP)        │
│  (Rust, live)  │              │    (Python, new)    │
│                │              │                     │
│  get-function  │              │  meta_info          │
│  get-callers   │              │  form_info          │
│  find-symbol   │              │  skd_info           │
│  search-func   │              │  role_info          │
│  read-file     │              │  subsystem_info     │
│  ...           │              │  cf_info            │
│                │              │  cfe_diff           │
│                │              │  *-validate         │
└─────┬──────────┘              └─────────────────────┘
      │
┌─────▼──────────┐
│  index data    │
│  (source-      │
│   mirror)      │
└────────────────┘
```

**Принцип:** skills-bridge — это **семантический слой** над source-mirror. Он не дублирует code-index-mcp (который индексирует BSL и строит граф вызовов), а добавляет **интроспекцию XML-метаданных** — то, что code-index-mcp не делает.

---

## 6. Обновление BORROWING_MAP.md

### Новый раздел (вставить после §1 P0 — Интеграция):

```markdown
### cc-1c-skills — детальная интеграция

**Репозиторий:** `tools/cc-1c-skills/` (подмодуль)
**Ветка для MCP:** `port-claude-code-py` (Python-скрипты)
**Ветка по умолчанию:** `main` (PowerShell-скрипты)

**Что берём:**
- Логику `*-info` скриптов (Python) — адаптируем под FastMCP-инструменты
- Логику `*-validate` скриптов (Python) — адаптируем под quality-gate MCP-инструменты
- SKILL.md как reference для промпт-дизайна
- Формат frontmatter (name, description, argument-hint, allowed-tools) — как reference для наших skills

**Что НЕ берём:**
- PowerShell-скрипты (используем Python-версию для кросс-платформенности MCP)
- Write-операции (edit, compile, remove, add) — оставляем для Phase B
- Live-режим skills (db-*, web-*) — оставляем для Phase B live-1c-bridge
- Скрипты без Py-реализации (db-list, epf-bsp-*, erf-build, form-patterns, web-test)

**Аттрибуция:**
- `tools/skills-bridge/ATTRIBUTION.md` — ссылка на оригинальный проект
- `tools/skills-bridge/README.md` — "Based on cc-1c-skills by Nikolay-Shirokov (MIT)"
- Комментарии в каждом adapted tool: `# Adapted from cc-1c-skills/scripts/<name>.py (MIT)`
- Integration card: `## Sources` с лицензией и ссылкой

**Лицензионные границы:**
- MIT разрешает: копировать, модифицировать, распространять с указанием авторства
- Наш MCP-adapter — производная работа, остаётся MIT
- Не удалять LICENSE из `tools/cc-1c-skills/`
- Не выдавать оригинальные skills за свои
```

---

## 7. Чеклист перед коммитом

- [ ] `docs/cc-1c-skills-analysis.md` создан и содержит все 6 разделов
- [ ] `docs/legal/BORROWING_MAP.md` обновлён разделом cc-1c-skills
- [ ] Все 68 навыков каталогизированы с pack и priority
- [ ] Топ-10 P0 определён и обоснован
- [ ] План внедрения содержит 4 фазы с конкретными артефактами
- [ ] Аттрибуция Nikolay-Shirokov указана во всех документах
- [ ] Нет скопированного текста из SKILL.md без пометки "(MIT, cc-1c-skills)"
