# Contributing to 1c-ai-workbench

Thank you for your interest in contributing. This document explains how to
get involved.

## Code of Conduct

All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Be respectful, technical, and constructive.

## Quick start

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Install pre-commit: `pip install pre-commit && pre-commit install`
4. Make your changes.
5. Run `pre-commit run --all-files` before committing.
6. Push and open a Pull Request against `main`.

## Ground rules

- All commits must pass CI. CI runs: secret scan (gitleaks), Python lint
  (ruff, black, mypy), Rust build/test (cargo fmt, clippy, test), PowerShell
  smoke checks, license compliance (REUSE), markdown lint, pre-commit
  (all hooks), and CodeQL.
- All new Python modules must include SPDX headers. Use the REUSE tool:
  `reuse addheader --copyright="1c-ai-workbench contributors" --license=MIT
  path/to/file.py`.
- PRs without passing CI will not be merged. If a CI failure is unrelated to
  your change, mention it in the PR description.
- Public discussions happen in GitHub Issues and Pull Requests. Do not
  share customer data, dump files, or API keys in public channels.
- Security issues: see [SECURITY.md](SECURITY.md) and the security issue
  template. **Do not** open a public issue for security vulnerabilities.

## Repository layout

- `tools/code-index-mcp/` — Rust MCP server (bsl-indexer)
- `tools/skills-bridge/` — Python FastMCP, read-only 1C introspection
- `tools/prompt-gallery/` — Python FastMCP, callable prompts
- `tools/help-index-mcp/` — Python FastMCP, local 1C .hbk search
- `tools/ibcmd-bridge/` — Python FastMCP, Phase B, disabled by default
- `tools/live-1c-bridge/` — C# experimental live bridge
- `tools/cc-1c-skills/` — vendored git subtree (MIT, Nikolay-Shirokov;
  see `tools/SUBTREE.md` for sync workflow and pinned SHA)
- `scripts/` — PowerShell entry points
- `docs/` — documentation, ADRs, legal
- `prompts/` — prompt files
- `configs/` — integration packs, default config
- `rules/` — path-scoped AI rules

## Coding standards

- **Python:** ruff for lint, black for format, mypy for types. Line length 100.
  Prefer `pathlib` over `os.path`. Type hints on public functions.
- **Rust:** clippy with `-D warnings`, rustfmt default. Use `?` for error
  propagation, `thiserror` for error types.
- **PowerShell:** PSScriptAnalyzer, approved verbs (Get/Set/Add/Remove/etc.),
  avoid aliases, use `ShouldProcess` for state-changing functions.
- **Markdown:** markdownlint-cli2, see `.markdownlint.jsonc`. Reference-style
  links preferred for portability.
- **Commits:** conventional commits (`feat:`, `fix:`, `chore:`, `docs:`,
  `refactor:`, `test:`, `security:`). Imperative mood, ≤72 char subject.

## Testing

- Add tests for any new feature or bug fix.
- Python: pytest in the same directory as the code, `test_<module>.py`.
- Rust: `cargo test`, prefer integration tests for public APIs.
- PowerShell: Pester is welcome for non-trivial scripts.
- Pre-commit hooks must pass locally before push.

## Contributor License Agreement (CLA)

By contributing, you grant the maintainer a perpetual, worldwide,
non-exclusive, royalty-free license to use, reproduce, modify, distribute,
and sublicense your contribution under any license the project chooses,
including commercial licenses. See [CLA.md](CLA.md) for the full terms.

**Process:** after submitting a PR, comment with "I have read the CLA
and agree to its terms." No external contribution is merged without
CLA acknowledgment.

You also confirm that your contributions do not include code from
non-permissive-licensed projects without explicit attribution.
See [docs/legal/BORROWING_MAP.md](docs/legal/BORROWING_MAP.md)
for the borrowing policy.

For DCO (Developer Certificate of Origin) sign-off, include
`Signed-off-by: Your Name <your.email@example.com>` in each commit
message.

## Need help?

Open a GitHub Discussion or Issue. For security issues, follow
[SECURITY.md](SECURITY.md).
