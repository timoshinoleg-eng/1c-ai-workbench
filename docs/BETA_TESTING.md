# Beta-тестирование 1C AI Workbench v0.10.0-beta.1

> Публичная **unsigned beta** для знакомства с продуктом и сбора отзывов.
> Это не production-релиз: installer **не имеет коммерческой Authenticode-подписи**.
> Прежде чем запускать файл, сверьте SHA-256 и GitHub Actions run (инструкции ниже).
> Никогда не отключайте Windows Defender или SmartScreen.

## За 30 секунд

**Какую проблему решает.** Командам 1С постоянно нужны быстрые ответы по
конфигурации: где записывается регистр, какому объекту принадлежит форма,
какие процедуры экспортирует модуль, что изменилось между выгрузками, где
вручную проверить найденное место. 1C AI Workbench индексирует XML-выгрузку
конфигурации **локально** и отдаёт структурированные ответы через MCP-клиент
(opencode, Cursor, VS Code, desktop MCP client) с доказательствами: путь к
файлу, объект, процедура, фрагмент кода, уровень уверенности.

**Кому полезен.** 1С-разработчикам, техлидам, аналитикам и партнёрам, которые
хотят быстро ориентироваться в чужой или большой конфигурации и получать от AI
не догадки, а локальные доказательства из реальной выгрузки.

**Что вы сможете сделать после запуска.** Открыть интерактивный launcher,
проверить готовность стенда healthcheck'ом, выполнить локальный поиск по
безопасному demo-материалу и подключить MCP-серверы к своему AI-клиенту.

**Минимальный путь:** скачать installer из GitHub Release → сверить SHA-256 →
установить → открыть demo → получить первый результат. Пошагово — ниже.

**Важно.** Beta предназначена для работы с **экспортированными выгрузками и
демо-данными**. Не подключайте её к боевой production-базе 1С без резервной
копии; по умолчанию продукт работает в read-only режиме и не пишет в 1С.

**Куда отправлять отзыв.** См. раздел «Как отправить bug report» внизу этой
страницы. Не прикладывайте клиентские базы, токены и секреты.

---

## 1. Что нужно перед установкой

- Windows 10/11 x64.
- PowerShell 5.1+ (входит в Windows).
- **64-bit CPython 3.11** (обязательно для offline-установки Python-зависимостей;
  см. «Известные ограничения beta»).
- Git for Windows (для части сценариев зеркалирования).
- Файлы выгрузки конфигурации 1С в `C:\1c-ai-client\dump` — только если вы
  хотите индексировать собственную конфигурацию. Для первого знакомства
  достаточно встроенного demo-материала.

## 2. Скачать и проверить источник

1. Откройте GitHub Release `v0.10.0-beta.1` репозитория
   `timoshinoleg-eng/1c-ai-workbench`.
2. Убедитесь, что релиз помечен как **Pre-release**.
3. Скачайте файлы:
   - `1c-ai-workbench-setup-0.10.0-beta.1.exe` (installer);
   - `checksums.txt` (SHA-256 всех файлов релиза);
   - `beta-manifest.json` (метаданные сборки);
   - `bsl-indexer.exe` и отчёты `code-index-045-contract.json`,
     `prism-1c-eval.json`, `prism-1c-eval.md`.

### Проверка SHA-256 installer'а

В PowerShell, в папке со скачанным installer'ом:

```powershell
Get-FileHash .\1c-ai-workbench-setup-0.10.0-beta.1.exe -Algorithm SHA256
```

Сравните полученный хеш со строкой для
`1c-ai-workbench-setup-0.10.0-beta.1.exe` в `checksums.txt`. Хеш должен
совпасть полностью. Чтобы сверить весь релиз одной командой:

```powershell
Get-Content .\checksums.txt | ForEach-Object {
  $hash, $name = ($_ -split '\s{2}', 2)
  $actual = (Get-FileHash -LiteralPath $name -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $hash) { Write-Output "MISMATCH: $name" } else { Write-Output "OK: $name" }
}
```

Если хотя бы один хеш не совпал — **не запускайте файлы**, удалите их и сообщите
сопровождающему (см. «Как отправить bug report»).

### Проверка GitHub Actions run

Каждый файл релиза собран конкретным запуском GitHub Actions. Чтобы убедиться,
что артефакты произведены официальным workflow из зафиксированного коммита:

1. В `beta-manifest.json` найдите поля `run_id`, `commit_sha`, `workflow`
   (`build-beta-candidate.yml`), `repository`, `version`.
2. Откройте в браузере:
   `https://github.com/timoshinoleg-eng/1c-ai-workbench/actions/runs/<run_id>`.
3. Убедитесь, что run завершён со статусом **success**, относится к workflow
   `Build unsigned beta candidate`, к репозиторию
   `timoshinoleg-eng/1c-ai-workbench` и к ветке `main`.
4. Сравните `commit_sha` из манифеста с коммитом, на который указывает тег
   `v0.10.0-beta.1`.

Через GitHub CLI:

```powershell
gh run view <run_id> --repo timoshinoleg-eng/1c-ai-workbench
```

Дополнительно финальные публичные артефакты можно **вручную** проверить через
VirusTotal. Учитывайте: загруженные файлы могут стать доступны исследователям
безопасности, поэтому не загружайте туда собственные конфиденциальные данные —
только публичные файлы релиза.

## 3. Честно про Unknown publisher и SmartScreen

Эта beta **не имеет коммерческой Authenticode-подписи**. Поэтому:

- Windows SmartScreen может показать **«Неизвестный издатель»**
  (Unknown publisher) или «Windows защитил ваш компьютер».
- Это ожидаемое поведение для неподписанного installer'а и **не означает**,
  что файл вредоносный.
- Мы намеренно **не** используем self-signed сертификат и **не** имитируем
  Authenticode: честный статус «unsigned» важнее видимости подписи.

**Порядок действий безопасного тестировщика:**

1. Сначала сверите источник и SHA-256 (раздел 2).
2. Проверьте GitHub Actions run (раздел 2).
3. Только после успешной сверки источника и контрольных сумм, если вы доверяете
   источнику, можно нажать **«Подробнее» → «Выполнить в любом случае»**
   (More info → Run anyway) в SmartScreen.

**Никогда не отключайте Windows Defender, SmartScreen или другие средства
защиты ради запуска этой beta.** Если защита блокирует файл даже после сверки —
остановитесь и сообщите сопровождающему.

## 4. Установка

Installer — per-user (не требует прав администратора), по умолчанию ставится в
`%LOCALAPPDATA%\1c-ai-workbench`.

```powershell
.\1c-ai-workbench-setup-0.10.0-beta.1.exe
```

После установки создайте Python-окружение из проверенного offline-wheelhouse
(требуется 64-bit CPython 3.11):

```powershell
cd "$env:LOCALAPPDATA\1c-ai-workbench"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1 -Offline -SkipBinaryDownload
```

Offline-режим проверяет каждую wheel по `offline-wheelhouse\SHA256SUMS.txt`,
использует hash-locked `requirements-production.lock`, передаёт pip
`--no-index` и не обращается к сети.

## 5. Открыть demo и получить первый результат

Проверить готовность стенда:

```powershell
.\scripts\06_healthcheck.ps1
```

Ожидается: все проверки `[OK]` и отчёт `generated\reports\readiness-report.md`.

Открыть demo-витрину:

```powershell
.\scripts\11_open_demo_showcase.ps1
```

Demo-материалы лежат в `demo-showcase\index.html` и
`demo-questions\questions_partner_demo.md`.

Локальный поиск без AI по безопасному demo-фикстчурe:

```powershell
.\scripts\04_index_1c_dump.ps1 `
  -DumpRoot ".\tools\cc-1c-skills\tests\skills\cases\interface-edit\snapshots\basic" `
  -Force
.\tools\code-index-mcp\target\release\bsl-indexer.exe search-text "Форма" `
  --path ".\generated\index\source-mirror" --limit 5
```

Хороший результат: есть путь к файлу, совпадения по объекту/модулю, результат
можно открыть руками.

Запустить интерактивный launcher:

```powershell
.\START_HERE.ps1
```

Подключить MCP-серверы к своему AI-клиенту можно по
[`OPENCODE_SETUP_RU.md`](OPENCODE_SETUP_RU.md) или
[`MCP_SETUP_ASSISTANT.md`](MCP_SETUP_ASSISTANT.md).

Больше сценариев — в [`FIRST_10_MINUTES.md`](FIRST_10_MINUTES.md).

## 6. Privacy и data-flow

**Что остаётся локально:**

- ваша 1С-выгрузка в `C:\1c-ai-client\dump`;
- зеркало `generated\index\source-mirror`;
- SQLite-индекс `.code-index\index.db`;
- артефакты сборки `tools\code-index-mcp\target`;
- логи `logs\`.

Скрипты **не загружают** вашу выгрузку ни в какой внешний API или облако.
Индексация выполняется локально.

**Что может покинуть машину.** Если ваш MCP-клиент (Cursor, VS Code, opencode,
desktop MCP client) отправляет полученные фрагменты кода внешнему AI-провайдеру,
эти фрагменты могут уйти провайдеру согласно настройкам вашего клиента и
аккаунта. Это контролируется **вашим клиентом**, а не скриптами workbench.
API-ключи принадлежат вам; не храните реальные ключи в репозитории, отчётах или
скриншотах.

Подробнее — [`SECURITY_NOTES.md`](SECURITY_NOTES.md) и
[`BETA_SECURITY.md`](BETA_SECURITY.md).

## 7. Удаление программы

1. Запустите `Uninstall 1C AI Workbench` из меню Пуск (или
   `%LOCALAPPDATA%\1c-ai-workbench\unins000.exe`).
2. Установленные файлы приложения, ярлыки и регистрация в реестре удаляются.
3. Воспроизводимое Python-окружение `.venv` и кэши удаляются.
4. Пользовательские `generated\` и `logs\` **сохраняются** намеренно. Удалите
   их вручную, когда индексы, отчёты и диагностика больше не нужны:

```powershell
Remove-Item "$env:LOCALAPPDATA\1c-ai-workbench\generated" -Recurse -Force
Remove-Item "$env:LOCALAPPDATA\1c-ai-workbench\logs" -Recurse -Force
```

Beta использует изолированный AppId, отличный от production, поэтому её
удаление не затрагивает возможную production-установку.

## 8. Известные ограничения beta

- **Нет Authenticode-подписи.** SmartScreen покажет «Неизвестный издатель».
  Это ожидаемо; сверяйте SHA-256 и GitHub Actions run перед запуском.
- **Требуется 64-bit CPython 3.11.** Offline-установка Python-зависимостей
  использует системный интерпретатор; installer не бандлит Python.
- **Нет portable ZIP.** Честный portable-пакет «без Python и dev-инструментов»
  технически не готов: приложению нужен интерпретатор CPython 3.11 для
  создания `.venv` и запуска MCP-серверов, а installer его не содержит. Мы
  намеренно не публикуем фиктивный ZIP. Portable-сборка — отдельная будущая
  работа.
- **Не для production-баз без резервной копии.** Работайте только с
  экспортированными выгрузками и демо-данными. Продукт read-only по умолчанию и
  не пишет в 1С, но операционные ошибки вокруг живых баз — лишний риск.
- **Возможны предупреждения и шероховатости.** Beta может показывать
  предупреждения SmartScreen и содержать ошибки; мы не обещаем их отсутствие.
- **Live `ibcmd` write-операции выключены** по умолчанию и не входят в
  публичную beta.
- **Только Windows 10/11 x64.**

## 9. FAQ для тестировщика

**Это безопасно?** Продукт локальный и read-only, не пишет в 1С и не загружает
вашу выгрузку наружу. Но installer неподписан: безопасность запуска
подтверждается сверкой SHA-256 и GitHub Actions run, а не подписью.

**Нужен ли AI-клиент?** Для локального поиска и healthcheck — нет. Для
AI-ответов нужен MCP-совместимый клиент и ваш собственный API-ключ.

**Можно ли работать без интернета?** Да. Offline-установка и локальная
индексация не требуют сети. Сеть нужна только вашему AI-клиенту.

**Почему SmartScreen ругается?** Потому что beta неподписана. Это не признак
вируса. Сверьте источник и контрольные суммы; не отключайте защиту.

**Можно ли ставить рядом с production-версией?** Beta использует отдельный
AppId и не перезаписывает production-установку. Тем не менее рекомендуем
удалить beta перед установкой production, чтобы избежать путаницы.

**Индексирует ли beta мою базу напрямую?** Нет. Она работает с XML-выгрузкой
конфигурации, которую вы экспортируете сами. Исходная выгрузка не изменяется.

**Куда писать о проблемах?** См. раздел ниже. Без клиентских баз, токенов и
секретов.

## 10. Как отправить bug report

Откройте issue в репозитории `timoshinoleg-eng/1c-ai-workbench` или свяжитесь с
сопровождающим. Используйте шаблон ниже.

**Никогда не прикладывайте:**

- клиентские базы 1С и их выгрузки с реальными/персональными данными;
- API-ключи, токены, пароли, сертификаты;
- содержимое `.env`, `configs\external-client.env`, секретных файлов;
- полные логи, если в них могут быть секреты (обрезайте/затирайте).

**Прикладывайте безопасно:**

```text
Версия beta: v0.10.0-beta.1
Commit SHA (из beta-manifest.json): <40 hex>
GitHub Actions run ID: <run_id>
SHA-256 installer'а (Get-FileHash): <hash>
Windows: 10/11, x64, версия/сборка
Python: 3.11.x (64-bit)
Что делали (шаги):
  1.
  2.
Что ожидали:
Что произошло:
Сообщение об ошибке (без секретов):
Запись SmartScreen (текст/скриншот без личных данных):
```

## Связанные документы

- [`BETA_SECURITY.md`](BETA_SECURITY.md) — модель доверия и безопасности beta.
- [`FORUM_BETA_ANNOUNCEMENT.md`](FORUM_BETA_ANNOUNCEMENT.md) — шаблон поста для
  форумов.
- [`BETA_VERIFICATION_RECORD_TEMPLATE.md`](BETA_VERIFICATION_RECORD_TEMPLATE.md)
  — шаблон verification record.
- [`WINDOWS_EXE_INSTALLER.md`](WINDOWS_EXE_INSTALLER.md) — детали installer'а.
- [`SECURITY_NOTES.md`](SECURITY_NOTES.md) — что локально, что уходит наружу.
- [`FIRST_10_MINUTES.md`](FIRST_10_MINUTES.md) — быстрый сценарий.
- [`RELEASE_CONTRACT_V1.md`](RELEASE_CONTRACT_V1.md) — signed
  production-контракт (beta его не заменяет).
