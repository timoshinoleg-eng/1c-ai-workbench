# Первый запуск в корпоративной среде

Этот документ предназначен для технического специалиста пилота, который разворачивает 1C AI Workbench на изолированной или управляемой Windows-машине. Workbench работает локально и в default-сценариях не изменяет исходную XML-выгрузку 1С и не подключается к production ИБ для записи.

## До начала работы

Проверьте наличие Windows 10/11, PowerShell 5.1+, Git for Windows, CPython 3.10+ и права на запись в каталог workbench и выбранный локальный каталог dump. Для offline-wheelhouse текущий поддерживаемый профиль — **CPython 3.11 x64**; при другой версии Python используйте согласованный online-install либо подготовьте wheelhouse для целевой платформы.

Не размещайте dump на сетевом UNC-пути. `START_HERE.ps1` принимает только абсолютный локальный путь диска, например `C:\1c-ai-client\dump`.

## ExecutionPolicy

Не задавайте `Unrestricted` и не меняйте MachinePolicy/LocalMachine без требования вашей организации. Сначала проверьте эффективную политику:

```powershell
Get-ExecutionPolicy -List
```

Если политика домена не запрещает изменение CurrentUser, используйте:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Если доменная Group Policy принудительно задаёт `Restricted` или `AllSigned`, не обходите её самостоятельно. Передайте команде ИБ запрос с хешем release artifact, ссылкой на публичный source tag и этим документом. Одноразовый `-ExecutionPolicy Bypass` допустим только если его прямо разрешила корпоративная политика и оператор зафиксировал это в протоколе пилота.

## Проверка release artifact

Для каждого пилотного artefact выполните:

1. Сверьте SHA-256 файла с опубликованным `.SHA256SUMS.txt`.
1. Запустите `bsl-indexer.exe --version` и сохраните вывод в evidence-пакет.
1. На Windows проверьте Authenticode:

```powershell
Get-AuthenticodeSignature .\bsl-indexer.exe | Format-List Status,StatusMessage,SignerCertificate
```

1. Зафиксируйте release tag, commit, hash, дату и результат smoke check в форме из [RELEASE_EVIDENCE.md](RELEASE_EVIDENCE.md).

Не используйте artifact с несоответствующим hash, недействительной подписью или непонятным источником.

## Proxy и сетевой режим

Online setup требует доступа к GitHub Releases и Python package index. Для корпоративного proxy согласуйте endpoint, а затем задайте только session-level переменные, не записывая пароль в репозиторий:

```powershell
$env:HTTPS_PROXY = "http://proxy.company.local:8080"
$env:HTTP_PROXY = $env:HTTPS_PROXY
.\scripts\setup.ps1
```

Если выход в интернет запрещён, используйте подготовленный offline-wheelhouse и уже верифицированный release artifact. Список зависимостей и hashes должен соответствовать release evidence.

## Endpoint protection и App Control

Новый Rust executable может требовать allowlist со стороны Microsoft Defender, AppLocker, WDAC или корпоративного endpoint protection. Предоставьте службе ИБ следующие evidence: SHA-256, Authenticode result, release URL, source tag/commit, назначение бинаря и локальный путь установки.

Добавляйте правило по издателю/подписи, если это допускает политика, а не широкое исключение по каталогу или отключение защиты. После обновления binary повторите сверку hash и подписи.

## Установка и минимальная проверка

```powershell
cd <workbench-root>
.\scripts\setup.ps1
.\scripts\01_check_env.ps1
.\scripts\16_check_skills_bridge.ps1
.\scripts\17_check_ibcmd_bridge.ps1
.\scripts\18_check_prompt_gallery.ps1
.\scripts\04_index_1c_dump.ps1 -DumpRoot "C:\1c-ai-client\dump" -Force
.\scripts\06_healthcheck.ps1
```

Только после успешного healthcheck настраивайте MCP-клиент. См. [MCP setup assistant](MCP_SETUP_ASSISTANT.md) и [technical setup](TECHNICAL_SETUP.md).

## Восстановление и поддержка

При неуспешной установке не удаляйте логи и evidence. Соберите версию Python, PowerShell, Git, release tag/hash, точную команду, обезличенный вывод ошибки и результат `scripts\06_healthcheck.ps1`. Для очистки generated-артефактов используйте только `scripts\07_clean_generated.ps1`; не удаляйте исходный dump без отдельного согласования.
