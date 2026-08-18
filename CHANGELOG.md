# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security and enterprise readiness

- Replaced implicit `locals()` forwarding in public ibcmd MCP wrappers with explicit validated payloads.
- Restricted `ibcmd_exe` selection to server-side `IBCMD_EXE` policy and redacted absolute workbench paths in bridge responses.
- Validated `START_HERE.ps1` dump paths before directory creation; UNC, device and relative paths are rejected.
- Added enterprise first-run, release evidence, pilot runbook, acceptance checklist, script catalog and feature-gap documentation.
- Added Python CI coverage for bridge security and enterprise delivery contracts.

- Public open-core release.
- Builds and releases `bsl-indexer.exe` as the primary public asset.
- MCP server surface: code-index, skills-bridge, prompt-gallery, help-index, ibcmd-bridge.
- Healthcheck and E2E smoke pipeline.
