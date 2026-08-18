# Pilot Runbook

## Назначение

Runbook описывает техническое развёртывание ограниченного on-premise пилота 1C AI Workbench. Он не заменяет договор, commercial proposal, SLA или решение ИБ заказчика. Default-поток ограничивается локальной XML-выгрузкой, read-only индексированием и MCP-навигацией.

## Роли

| Роль | Ответственность |
|---|---|
| Заказчик: владелец пилота | Предоставляет test dump, принимает критерии и назначает пользователей |
| Заказчик: ИБ/endpoint team | Согласует ExecutionPolicy, proxy, App Control/AV rule и signing evidence |
| Заказчик: 1С-разработчик | Проверяет BSL/metadata результаты и вручную подтверждает бизнес-контекст |
| Поставщик: technical owner | Передаёт release evidence, консультирует по установке и ведёт журнал исключений |

## Предпосылки

До совместной сессии согласуйте локальный путь dump, допустимый release tag, hash artifact, режим сети (online/offline), MCP-клиент и контакт ИБ. Не используйте production credentials в demo/MCP конфигурации. Если нужна Phase B функция `ibcmd`, включайте её только в отдельной контролируемой проверке; write path по умолчанию заблокирован.

## Сценарий развёртывания

1. Проведите release verification по [RELEASE_EVIDENCE.md](RELEASE_EVIDENCE.md).
2. Выполните prerequisites и ExecutionPolicy checks по [ENTERPRISE_FIRST_RUN.md](ENTERPRISE_FIRST_RUN.md).
3. Склонируйте или распакуйте согласованный source/release bundle в локальный каталог пользователя.
4. Запустите `scripts\setup.ps1` и сохраните результат.
5. Прогоните три bridge smoke checks и `scripts\06_healthcheck.ps1`.
6. Поместите обезличенную/согласованную XML-выгрузку в локальный dump folder и выполните `scripts\04_index_1c_dump.ps1`.
7. Подключите MCP-клиент согласно [MCP_SETUP_ASSISTANT.md](MCP_SETUP_ASSISTANT.md).
8. Выполните demo-вопросы и зафиксируйте ответы, evidence snippets и ручную 1С-проверку.

## Контрольные точки

| Точка | Доказательство | Stop condition |
|---|---|---|
| Artifact verified | SHA-256, version, signer evidence | Hash/подпись не соответствуют policy |
| Setup completed | `.venv`, dependency report, no secrets in log | Proxy/ExecutionPolicy/endpoint protection блокируют установку |
| Read-only healthcheck | `6/6 Ready` или утверждённый эквивалент | Любой bridge пишет вне generated/workbench scope |
| Index completed | Индекс создан, source dump не изменён | XML dump невалиден или индексатор завершился с ошибкой |
| MCP demo | Ответ содержит object/module/evidence/manual check | Ответ не подтверждается исходными данными |
| Handoff | Acceptance checklist и logs переданы владельцу | Нет владельца evidence или открытых exceptions |

## Typical troubleshooting

| Симптом | Проверка | Безопасное действие |
|---|---|---|
| Скрипт не запускается | `Get-ExecutionPolicy -List` | Следовать enterprise first-run; не делать глобальный bypass |
| Binary заблокирован | Defender/AppLocker/WDAC event | Передать hash, signer, release evidence в ИБ |
| Нет доступа к GitHub/PyPI | Proxy/firewall log | Использовать approved proxy либо offline wheelhouse |
| `ibcmd` не найден | `IBCMD_EXE`, `ibcmd --version` | Настроить путь на сервере MCP, не передавать произвольный exe через клиент |
| Индексация не проходит | Dump format и report | Не модифицировать dump; запустить диагностический script и приложить logs |
| MCP вернул путь/секрет | Bridge version и sanitized log | Остановить пилот, обновить bridge, приложить security record |

## Handoff

Перед завершением пилота соберите release evidence, healthcheck, E2E/smoke result, index version, список MCP tools, замечания пользователей, acceptance checklist и список исключений. Не включайте в пакет XML dump, production credentials или необезличенные логи без отдельного разрешения.
