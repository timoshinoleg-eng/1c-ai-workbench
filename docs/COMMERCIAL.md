# 1C AI Workbench — Commercial Pilots

## Public core и коммерческая поставка

Публичный core распространяется под MIT и включает локальный read-only workbench, инструменты навигации и аудита XML-выгрузки, документацию по воспроизводимой установке и исходники indexer/bridges. Пилотная поставка может дополнительно включать curated prompt packs, golden-answer corpus, технический security playbook, acceptance workshop, named support channel и методологию внедрения.

Коммерческая поставка не должна изменять заявленные границы продукта: default-поток остаётся offline-first и read-only, исходная XML-выгрузка не модифицируется, а live/write возможности `ibcmd` выключены по умолчанию.

## Рекомендуемый контур пилота

| Этап | Технический результат |
|---|---|
| Discovery | Согласованы dump, target environment, network mode, MCP-клиент и security contacts |
| Readiness | Release evidence, endpoint/ExecutionPolicy decision и prerequisites подтверждены |
| Installation | Workbench установлен, bridges и healthcheck прошли |
| Index & demo | XML dump проиндексирован; demo-вопросы подтверждены 1С-разработчиком |
| Acceptance | Заполнен [technical acceptance checklist](PILOT_ACCEPTANCE_CHECKLIST.md), exceptions имеют владельца |
| Handoff | Заказчику переданы runbook, evidence и безопасный recovery path |

Подробный технический путь описан в [PILOT_RUNBOOK.md](PILOT_RUNBOOK.md). Корпоративный first-run, proxy/offline и endpoint controls описаны в [ENTERPRISE_FIRST_RUN.md](ENTERPRISE_FIRST_RUN.md).

## Что согласует владелец до коммерческого предложения

Цена, срок, объём named support, SLA, режим обработки персональных данных, перечень поддерживаемых платформ и условия офлайн-поставки зависят от конкретного пилота. Они намеренно не фиксируются в публичном репозитории до согласования владельцем продукта и заказчиком.

## Контакт

Для запроса пилота укажите предполагаемый масштаб XML-выгрузки, режим сети, целевой MCP-клиент, требования ИБ и желаемый сценарий демо. Контакт: **[maintainer email / pilot form]**.
