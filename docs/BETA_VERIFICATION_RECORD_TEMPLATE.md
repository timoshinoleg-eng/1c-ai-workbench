# Beta Verification Record Template

> Шаблон verification record для публичной unsigned beta. Заполняется
> верификатором при проверке beta на чистой или максимально изолированной
> Windows-машине. Ссылка на заполненную запись передаётся в
> `publish-beta-verified.yml` как `verification_record`.
>
> Замените значения в `<...>` на фактические. Не включайте клиентские базы,
> токены и секреты.

## Идентификация сборки

- Репозиторий: `timoshinoleg-eng/1c-ai-workbench`
- Версия beta: `v0.10.0-beta.1`
- Commit SHA (из `beta-manifest.json`): `<40 hex>`
- GitHub Actions run ID (`build-beta-candidate.yml`): `<run_id>`
- URL run: `https://github.com/timoshinoleg-eng/1c-ai-workbench/actions/runs/<run_id>`
- Статус run: `<success>`
- Ветка run: `main`
- `release_channel` в манифесте: `beta`
- `signed` / `authenticode_present` в манифесте: `false` / `false`

## Контрольные суммы (SHA-256)

Заполните выводом `Get-FileHash -Algorithm SHA256` и сверкой с `checksums.txt`.

| Файл | SHA-256 | Совпадает с checksums.txt |
| --- | --- | --- |
| `1c-ai-workbench-setup-0.10.0-beta.1.exe` | `<hash>` | да/нет |
| `bsl-indexer.exe` | `<hash>` | да/нет |
| `code-index-045-contract.json` | `<hash>` | да/нет |
| `prism-1c-eval.json` | `<hash>` | да/нет |
| `prism-1c-eval.md` | `<hash>` | да/нет |
| `beta-manifest.json` | `<hash>` | да/нет |

## Среда проверки

- ОС: `<Windows 10/11, x64, версия/сборка>`
- Чистая/изолированная машина: `<да/нет, пояснение>`
- Python: `<3.11.x, 64-bit>`
- Права администратора: `<не использовались / использовались>`

## Проверка источника

- GitHub Actions run относится к `build-beta-candidate.yml`: да/нет
- Commit SHA манифеста совпадает с коммитом тега `v0.10.0-beta.1`: да/нет
- Commit является предком `origin/main`: да/нет
- Релиз помечен Pre-release: да/нет

## Authenticode и SmartScreen (честно)

- Authenticode-статус installer'а: `<NotSigned / иной>` (ожидаемо неподписан)
- Текст/поведение SmartScreen: `<описание>`
- Скриншот SmartScreen (без личных данных): `<ссылка/путь>`
- Defender оставлен включённым: да
- Перед запуском сверены источник и SHA-256: да/нет

## Установка и запуск

- Тихая/per-user установка без админ-прав: `<PASS/FAIL>`
- `scripts\setup.ps1 -Offline -SkipBinaryDownload`: `<PASS/FAIL>`
- `scripts\06_healthcheck.ps1`: `<n/n Ready>`
- `generated\reports\readiness-report.md` создан: да/нет
- `scripts\11_open_demo_showcase.ps1` открывает demo: `<PASS/FAIL>`
- Локальный поиск `bsl-indexer.exe search-text` по demo-фикстчурe: `<PASS/FAIL>`
- `START_HERE.ps1` запускается: `<PASS/FAIL>`

## MCP-проверка (опционально)

- `meta_info` на demo-фикстчурe: `<ответ/скриншот без секретов>`
- `form_info` на demo-фикстчурe: `<ответ/скриншот без секретов>`

## Удаление

- Uninstaller завершился успешно: `<PASS/FAIL>`
- Управляемые файлы приложения удалены: да/нет
- `.venv` и кэши удалены: да/нет
- `generated`/`logs` сохранены (политика): да/нет

## Вердикт

- Итог: `<ACCEPT / REJECT>`
- Замечания: `<список или "нет">`
- Дата и верификатор: `<YYYY-MM-DD, имя/псевдоним>`

## Правила заполнения

- Не прикладывайте клиентские базы 1С, реальные выгрузки с персональными
  данными, API-ключи, токены, пароли, сертификаты.
- Логи и скриншоты публикуйте только после проверки на секреты.
- Любой сбой целостности, подписи (ожидаемо неподписана), источника или
  функциональности фиксируется; при функциональном сбое требуется новая сборка,
  а не патч файлов на месте.
