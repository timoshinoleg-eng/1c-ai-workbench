# First 10 Minutes

Короткий сценарий, если стенд уже лежит локально и нужно быстро понять, что он живой и полезный.

## 1. Проверить готовность стенда

```powershell
cd C:\1c-ai-workbench
.\scripts\06_healthcheck.ps1
```

Ожидаемый результат:

- все проверки `[OK]`
- создан файл `generated\reports\readiness-report.md`

Если есть ошибки, сначала исправьте их по `Action` из readiness report.

## 2. Открыть readiness report

Откройте:

```text
C:\1c-ai-workbench\generated\reports\readiness-report.md
```

Смотрите три статуса:

- `local_search`
- `ai_client`
- `partner_demo`

Если `local_search=ready`, можно идти дальше даже без AI-клиента.

## 3. Выбрать быстрый сценарий по роли

### Для 1С-техлида

Файл:

```text
demo-questions\questions_1c_lead.md
```

### Для 1С-разработчика

Файл:

```text
demo-questions\questions_developer_workflow.md
```

### Для партнёра / демо

Файл:

```text
demo-questions\questions_partner_demo.md
```

## 4. Проверить локальный поиск без AI

```powershell
.\tools\code-index-mcp\target\release\bsl-indexer.exe search-text "Контрагенты" --path "C:\1c-ai-workbench\generated\index\source-mirror" --limit 5
```

Хороший результат:

- есть путь к файлу;
- есть совпадения по объекту или модулю;
- результат можно открыть руками.

## 5. Запустить первый осмысленный вопрос

Используйте expected format:

```text
demo-questions\expected_answer_format.md
```

Просите ответ так:

```text
Назови конкретный файл, найденное место, уверенность и как проверить руками.
Если точного места нет — скажи это прямо.
```

## 6. Сохранить результат

После первого рабочего прогона у вас уже есть:

- `logs\stats.json`
- `logs\smoke-search-text.txt`
- `generated\reports\readiness-report.md`

Этого достаточно, чтобы:

- показать партнёру, что стенд живой;
- передать состояние коллеге;
- вернуться к работе позже без повторной диагностики.
