# Beta Security and Trust Model

> Модель доверия публичной **unsigned beta** `v0.10.0-beta.1`.
> Этот документ описывает, почему beta устроена именно так, какие гарантии она
> даёт и чего намеренно не делает. Для пользовательских инструкций см.
> [`BETA_TESTING.md`](BETA_TESTING.md).

## Честный статус подписи

Beta **не имеет** коммерческой Authenticode-подписи. Это осознанное решение:

- мы **не** создаём self-signed сертификат;
- мы **не** имитируем Authenticode и не подделываем «доверенного издателя»;
- мы **не** советуем пользователям отключать Windows Defender, SmartScreen или
  иные средства защиты;
- мы **не** добавляем signing-секреты (PFX) в beta-контур.

Отсутствие подписи честно отражено в `beta-manifest.json` полями
`signed: false`, `authenticode_present: false` и в статусе Authenticode.
Отсутствие детектов антивируса **не** гарантирует отсутствие вредоносного кода;
доверие к beta строится на проверяемом происхождении и контрольных суммах, а не
на факте подписи.

## Отдельный beta-контур

Beta собирается отдельными workflow, которые не затрагивают signed-production
контур:

- `build-beta-candidate.yml` — собирает неподписанный installer из
  зафиксированного коммита `main`;
- `publish-beta-verified.yml` — публикует ровно проверенные файлы как
  Pre-release.

Production-контур (`build-candidate.yml`, `publish-verified.yml`,
[`RELEASE_CONTRACT_V1.md`](RELEASE_CONTRACT_V1.md)) не изменён и не ослаблен.
Beta-workflow не ссылаются на production-секреты и не используют защищённые
production-окружения.

## Гарантии сборки (fail-closed)

`build-beta-candidate.yml` завершается ошибкой, если:

- версия не является SemVer prerelease (например `0.10.0-beta.1`);
- `commit_sha` не является полным 40-символьным SHA;
- workflow запущен не из `refs/heads/main`, или HEAD не совпадает с запрошенным
  коммитом, или коммит не является текущим `origin/main`;
- не прошли обязательные тесты: `pytest`, `cargo test`, контракт code-index
  0.45, provider-free evaluation, тест installer'а;
- обязательные файлы отсутствуют;
- installer оказался подписан (beta должна быть unsigned — это проверяется
  явно).

Installer использует изолированный beta AppId, отличный от production, поэтому
beta-установка не может обновить, понизить или перезаписать production.

## Происхождение и целостность (provenance & integrity)

Каждый beta-артефакт содержит:

- `beta-manifest.json` — `schema_version`, `release_channel: beta`,
  `repository`, `workflow`, `run_id`, `commit_sha`, `version`, `app_id`,
  `signed: false`, `authenticode_present: false`, `signing_note`;
- `checksums.txt` — SHA-256 каждого файла артефакта.

`publish-beta-verified.yml` перед публикацией проверяет:

1. run произведён именно `build-beta-candidate.yml` в этом репозитории, из
   `main`, со статусом success;
2. существует ровно один непросроченный `beta-candidate-*` артефакт;
3. артефакт скачивается **без пересборки**;
4. манифест совпадает с запрошенным тегом/версией/run id/commit SHA;
5. манифест объявляет артефакт неподписанным;
6. каждый SHA-256 из `checksums.txt` совпадает, и все обязательные файлы
   покрыты контрольными суммами;
7. installer действительно не имеет валидной Authenticode-подписи;
8. commit является предком текущего `origin/main`;
9. существующий несовместимый тег или релиз отклоняется (без перезаписи);
10. GitHub Release создаётся только с флагом `--prerelease`.

Workflow ничего не пересобирает, не подписывает и не изменяет скачанные файлы.

## Data-flow и privacy

Локально остаются: 1С-выгрузка, её зеркало, SQLite-индекс, артефакты сборки и
логи. Скрипты не отправляют выгрузку во внешние API. Фрагменты кода могут уйти
внешнему AI-провайдеру только через ваш MCP-клиент и согласно его настройкам;
это контролируется клиентом, а не workbench. API-ключи принадлежат оператору.
Подробности — [`SECURITY_NOTES.md`](SECURITY_NOTES.md) и
[`SECURITY_OVERVIEW.md`](SECURITY_OVERVIEW.md).

## Ручная проверка антивирусом

Финальные публичные артефакты можно вручную проверить через VirusTotal.
Учитывайте: загруженные файлы могут стать доступны исследователям безопасности.
Загружайте только публичные файлы релиза, никогда — собственные конфиденциальные
данные, базы или секреты.

## Что сделало бы релиз production

Production-путь описан в [`RELEASE_CONTRACT_V1.md`](RELEASE_CONTRACT_V1.md):
реальный commercial Authenticode-сертификат, подписанный candidate, проверка тех
же файлов на чистой Windows и публикация без пересборки. Beta не заменяет этот
контракт и не снижает его требования.

## Ограничения доверия beta

- Нет подписи → SmartScreen покажет «Неизвестный издатель».
- Доверие основано на сверке источника (GitHub Actions run + тег) и SHA-256.
- Требуется 64-bit CPython 3.11; portable ZIP без Python не предоставляется.
- Beta не предназначена для production-баз без резервной копии.
