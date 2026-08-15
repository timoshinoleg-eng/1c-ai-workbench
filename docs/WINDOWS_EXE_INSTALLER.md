# Windows EXE Installer

The production Windows package is a per-user Inno Setup installer. Its default
location is `%LOCALAPPDATA%\1c-ai-workbench`; administrator privileges are not
required.

## Production boundary

The installer contains the workbench, `bsl-indexer.exe`, the exact Python
dependency lock, and an optional verified offline wheelhouse. It never bundles
proprietary 1C binaries, writes to a live 1C database, or installs optional
integration packs.

The target computer must already have 64-bit CPython 3.11. A production package
with the wheelhouse can create its virtual environment without network access:

```powershell
.\scripts\setup.ps1 -Offline -SkipBinaryDownload
```

Offline mode verifies every wheel against `offline-wheelhouse\SHA256SUMS.txt`,
uses the hash-locked `requirements-production.lock`, passes `--no-index` to pip,
does not upgrade pip, and does not download the indexer.

## Reproducible build

Install Inno Setup 6.7.3, build the Rust release binary, then run:

```powershell
.\scripts\23_prepare_offline_wheelhouse.ps1
.\scripts\19_build_windows_installer.ps1 `
  -AppVersion "0.9.0-rc1" `
  -OfflineWheelhouse ".\dist\offline-wheelhouse" `
  -RequireOfflineWheelhouse
```

The wheelhouse builder accepts only 64-bit CPython 3.11 on Windows, downloads
binary wheels from the hash-locked requirements, and writes wheel and lock
metadata. Generated wheels remain under `dist` and are not committed.

The build produces:

```text
dist\installer\1c-ai-workbench-setup-<version>.exe
dist\installer\1c-ai-workbench-setup-<version>.exe.sha256
```

## Authenticode signing

Unsigned builds are supported for local testing. Production publication is
fail-closed and requires a real code-signing certificate available in the
Windows certificate store:

```powershell
.\scripts\19_build_windows_installer.ps1 `
  -AppVersion "0.9.0" `
  -OfflineWheelhouse ".\dist\offline-wheelhouse" `
  -RequireOfflineWheelhouse `
  -SignCertificateThumbprint "<real certificate thumbprint>" `
  -RequireSignature
```

The build uses SHA-256 for the file digest, RFC 3161 timestamping, and validates
the resulting Authenticode signature before returning success. No placeholder
certificate or self-signed production substitute is accepted.

The GitHub release workflow additionally requires encrypted repository secrets
`WINDOWS_SIGNING_CERT_PFX_BASE64` and
`WINDOWS_SIGNING_CERT_PFX_PASSWORD`. It imports the certificate only on the
ephemeral runner, verifies the signed installer, publishes checksums, and removes
the temporary PFX and certificate afterward.

## Upgrade and uninstall policy

The production AppId is stable and `UsePreviousAppDir=yes`, so an installer with
a newer version upgrades the existing per-user installation in place.

An older numeric version is rejected by default. An approved emergency rollback
can explicitly pass `/ALLOWDOWNGRADE=1`; this must be treated as a controlled
operator action, not as the normal update path.

- Managed application files are replaced during upgrade.
- `generated` and `logs` are treated as user data and are preserved during both
  upgrade and uninstall.
- The reproducible `.venv` and Python cache directories are removed by
  uninstall.
- Installed application files, shortcuts, and registry registration are removed
  by Inno Setup.

The remaining `generated`/`logs` directory can be archived or deleted manually
after the user confirms that its indexes, reports, and diagnostics are no longer
needed.

## Automated acceptance

The following test uses an isolated temporary directory and a non-production
AppId, so it cannot overwrite an existing installation:

```powershell
.\scripts\24_test_windows_installer.ps1 `
  -InstallerPath ".\dist\installer-ci1\1c-ai-workbench-setup-0.9.0.1.exe" `
  -UpgradeInstallerPath ".\dist\installer-ci2\1c-ai-workbench-setup-0.9.0.2.exe"
```

It proves silent install, offline dependency installation, managed payload
presence, upgrade preservation, default downgrade rejection, runtime cleanup,
user-data preservation, and silent uninstall. CI also proves that
`-RequireSignature` rejects missing certificate material.

## External production prerequisite

> **Python contract.** The installer intentionally does not embed Python. Offline setup requires a **full 64-bit CPython 3.11 runtime** with `venv` and `ensurepip` available; the embeddable archive is not sufficient. A signed runtime may be staged offline before installation, and `scripts\setup.ps1` fail-closes if the required interpreter contract is absent.

The repository can prove all unsigned behavior and the fail-closed signing path.
Actual CA trust, timestamp availability, and Microsoft SmartScreen reputation
can only be verified after a real production Authenticode certificate is
provisioned. A production release must not be published until that signed run is
green.
