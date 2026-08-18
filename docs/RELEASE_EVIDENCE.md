# Release Evidence Guide

Этот документ фиксирует evidence, который должен сопровождать любой candidate или production release `bsl-indexer`. Он дополняет [RELEASE_CONTRACT_V1.md](RELEASE_CONTRACT_V1.md), но не заменяет требования подписи и approval из корпоративной политики.

## Обязательные данные release record

| Поле | Источник | Обязательное значение |
|---|---|---|
| Release tag | GitHub Release | Неизменяемый tag, указывающий на source commit |
| Target commit | Git tag / release metadata | Полный SHA commit |
| Artifact name | Release assets | Например, `bsl-indexer.exe` |
| SHA-256 | Release checksum asset | Полное значение SHA-256 |
| Version output | `bsl-indexer.exe --version` | Сохранённый stdout и exit code `0` |
| Signature result | `Get-AuthenticodeSignature` | Status, signer subject, thumbprint и timestamp |
| Clean-Windows smoke | Изолированная машина | Версии ОС/Python/PowerShell, команды и PASS/FAIL |
| Dependency notice | Release bundle | NOTICE/SBOM или эквивалентный список зависимостей |

## Локальная верификация

Для формирования машиночитаемого evidence record используйте `scripts\\28_collect_release_evidence.ps1`:

```powershell
.\\scripts\\28_collect_release_evidence.ps1 `
  -ArtifactPath .\\bsl-indexer.exe `
  -ReleaseTag v0.9.0-pilot `
  -TargetCommit <full-commit-sha> `
  -ExpectedSha256 <published-sha256>
```

Скрипт только читает artifact и пишет JSON-отчёт в `generated\\reports`; он не подписывает, не публикует и не изменяет binary. Для ручной проверки скачайте release assets в новый каталог, затем сравните hash:

```powershell
Get-FileHash .\bsl-indexer.exe -Algorithm SHA256
Get-Content .\bsl-indexer.exe.SHA256SUMS.txt
.\bsl-indexer.exe --version
Get-AuthenticodeSignature .\bsl-indexer.exe | Format-List Status,StatusMessage,SignerCertificate
```

SHA-256 должен совпадать с опубликованным checksum. Exit code команды `--version` должен быть `0`. Для signed production artifact статус Authenticode должен соответствовать политике организации. Если signature отсутствует у pilot artifact, record должен явно содержать `NOT SIGNED — PILOT ONLY`; не выдавайте такой artifact за signed production release.

## Clean-Windows smoke

На чистой Windows VM или endpoint без checkout разработчика выполните:

```powershell
.\scripts\setup.ps1
.\scripts\01_check_env.ps1
.\scripts\16_check_skills_bridge.ps1
.\scripts\17_check_ibcmd_bridge.ps1
.\scripts\18_check_prompt_gallery.ps1
.\scripts\22_run_e2e_smoke.ps1 -SkipIndex
```

Сохраните stdout/stderr, версии ОС, Python, PowerShell и hash самого binary. Не пересобирайте artifact между проверкой и публикацией.

## Шаблон evidence record

```text
release_tag:
target_commit:
artifact:
artifact_sha256:
version_stdout:
authenticode_status:
signer_subject:
signer_thumbprint:
timestamp_status:
clean_windows_host:
clean_windows_smoke:
notice_or_sbom:
verified_by:
verified_at_utc:
exceptions:
```

## Автоматизируемая часть

CI может автоматически публиковать hash, `--version`, source commit, SBOM/NOTICE и результат тестов. Authenticode-подпись, timestamping и clean-Windows verification требуют доступного сертификата, доверенной Windows runner/VM и release authority. Они остаются внешними gate и не должны имитироваться в CI.
