# Linting and quality gates

All blocking checks run in `.github/workflows/ci.yml`. Tool versions and GitHub
Actions are pinned so that a fresh runner produces the same result as a local
validation run.

## First-party code and documentation

The workbench-owned files are checked with:

- Ruff and Black for Python;
- markdownlint-cli2 for Markdown;
- PSScriptAnalyzer plus a parser and replacement-character check for
  PowerShell;
- Gitleaks for committed secrets;
- REUSE for copyright and license metadata;
- the standard pre-commit whitespace, syntax, and merge-conflict hooks.

PowerShell files are excluded from generic end-of-file and line-ending fixes.
Those hooks can damage encodings used by Windows entrypoints. PowerShell still
has blocking parser, U+FFFD, and PSScriptAnalyzer gates.

## Vendored snapshots

`tools/code-index-mcp` and `tools/cc-1c-skills` preserve their upstream history
and style. They are excluded from first-party Ruff, Black, Markdown, and generic
pre-commit formatting. This is a repository boundary, not a quality bypass:

- `tools/code-index-mcp` has a dedicated release build, Clippy correctness,
  suspicious-code and performance gates, the complete Rust test suite, and
  fixture-based integration tests;
- `tools/cc-1c-skills` supplies deterministic fixtures used by the PowerShell
  installation and indexing smoke test;
- both snapshots are covered by explicit upstream REUSE annotations.

Two Clippy API-size warnings in the vendored code-index API require architectural
changes and are allowed by name in the dedicated job. Correctness, suspicious-
code, and performance categories remain blocking; no category is disabled
globally.

## Local validation

Run the complete repository gate before a production-readiness commit:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check tools scripts
.venv\Scripts\black.exe --check tools scripts
.venv\Scripts\pre-commit.exe run --all-files --show-diff-on-failure
.venv\Scripts\reuse.exe lint
```

Run the vendored Rust gate separately:

```powershell
Set-Location tools\code-index-mcp
cargo clippy --all-targets -- -D clippy::correctness -D clippy::suspicious -D clippy::perf -A clippy::result_large_err -A clippy::large_enum_variant
cargo test --all --no-fail-fast -j 1
```
