# Windows EXE Installer

This project can be packaged as a Windows `.exe` installer with Inno Setup for
local deployments and controlled on-premise pilot / production v1 rollout.

## What the Installer Does

- Installs the workbench to `C:\1c-ai-workbench` by default.
- Creates `C:\1c-ai-client\dump` for 1C configuration exports.
- Creates Start Menu and optional Desktop shortcuts.
- Launches `START_HERE.ps1` through PowerShell with process-scoped execution bypass.
- Includes repository docs, configs, scripts, prompts, rules, demo files, and available packaged tools.
- Preserves the current default operating model: local, read-only, no automatic live writes.

## What the Installer Does Not Do

- It does not install third-party integration tools.
- It does not install Git, Python, Rust, 1C Platform, or MCP clients.
- It does not download binaries.
- It does not provide SaaS services or cloud hosting.
- It does not bundle proprietary 1C binaries.
- It does not include `.git`, `generated`, `logs`, `dist`, local agent folders, databases, secrets, or environment files.

## Build Requirement

Install Inno Setup 6 on the build machine:

```powershell
winget install JRSoftware.InnoSetup
```

Manual download is also fine: https://jrsoftware.org/isinfo.php

## Build Command

From the repository root:

```powershell
.\scripts\19_build_windows_installer.ps1
```

Optional version override:

```powershell
.\scripts\19_build_windows_installer.ps1 -AppVersion "0.1.0-phase-b"
```

Expected output:

```text
dist\installer\1c-ai-workbench-setup-<version>.exe
```

## Validation

The build wrapper checks:

- `START_HERE.ps1` exists.
- Inno Setup compiler `ISCC.exe` is available.
- `configs\integration-packs.json` is valid JSON.
- The generated installer exists after compilation.

The installer itself is intentionally an operational shell around the existing
workbench. It preserves the production v1 boundary: local read-only workbench,
controlled on-premise rollout, no bundled proprietary 1C binaries, and no
automatic installers for external tools.
