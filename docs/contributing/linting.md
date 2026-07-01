# v1.1 Linting Backlog

> Created 2026-06-23. Status: in progress.

## Summary

The pre-commit hooks in v1.0/v1.1.0-pre ran as **advisory** (manual stage) for the
linter family because the existing codebase has thousands of pre-existing style
issues. Tightening all of them at once would create a 100+-file diff and bury
real bugs in noise. This document tracks what needs to be fixed and when.

## Findings from v1.1.0-pre run

When ruff, ruff-format, codespell, markdownlint-cli2, and editorconfig-checker
were promoted to **blocking** (default stage) for one test run, the results were:

| Tool | Errors | Action |
|---|---|---|
| `ruff` (with E501/RUF001/RUF002/SIM108/UP031 ignored) | 18 | keep blocking — these are real issues |
| `ruff-format` | 0 | keep blocking — formatter enforces black-style format |
| `codespell` | ~30 in `tools/cc-1c-skills/**` (vendored subtree, deeply nested) | exclude more aggressively |
| `markdownlint-cli2` | 12,767 in 50+ files | too aggressive — needs tighter `.markdownlint.jsonc` and per-file excludes |
| `editorconfig-checker` | 1,712 — mostly PS-script 2-space indent vs `.editorconfig` 4-space | need different per-file `.editorconfig` for PS scripts |
| `mixed-line-ending` (already in standard hooks) | 20+ files | auto-fixed on first run, OK now |
| `trailing-whitespace` / `end-of-file-fixer` | hundreds | auto-fixed on first run, OK now |

## Decisions

### 1. Ruff config (in `pyproject.toml`)

Keep the following ignores in v1.1.0:
- `E501` — line too long. Code inherited from `cc-1c-skills` uses lines up to
  220 characters. Forcing a reformat would create a 70 KB diff with no functional
  benefit. We cap at `line-length = 125` in `pyproject.toml`, which is a
  practical upper bound for most new code.
- `RUF001` — ambiguous unicode characters. Russian Cyrillic in 1C paths and
  prompts triggers this. False positive for our domain.
- `RUF002` — class-without-metaclass. Legacy Python 2 / 1C convention.
- `SIM108` — use ternary operator. We prefer explicit if-else for readability
  in tools-bridge code.
- `UP031` — use format specifiers. Legacy `%` formatting accepted.

Remaining real issues (18 after above ignores) are `F401` (unused imports),
`F841` (unused variables), `B904` (raise from), etc. These are caught by ruff
in blocking mode and fixed in the auto-fix pass.

### 2. Codespell

The `exclude: ^tools/(cc-1c-skills|code-index-mcp|live-1c-bridge)/` pattern
does not match deeply nested files in those subdirectories. Codespell found
typos in `tools/cc-1c-skills/docs/1c-config-objects-spec.md` and similar.

**Action for v1.1.1:** change the exclude pattern to a path-prefix match that
covers the entire subtree. The simplest fix is to add `--skip` args with
`**/cc-1c-skills/docs/**` and `**/cc-1c-skills/tests/**` patterns.

### 3. Markdownlint

The `.markdownlint.jsonc` is currently too lenient in some rules and too strict
in others. Strict mode found 12,767 errors, mostly in inherited docs
(`tools/code-index-mcp/CHANGELOG_EN.md` is 145 KB and produces 2,000+ errors
on its own).

**Action for v1.1.1:** move large inherited docs (`CHANGELOG_EN.md`,
`tools/code-index-mcp/README*.md`) to a `docs/inherited/` allowlist, OR add
explicit per-file `disable` comments in those files.

### 4. EditorConfig

The `.editorconfig` says `[*.{ps1,psm1,psd1}] indent_size = 4`, but actual
PowerShell scripts use **2-space indent** (inherited from `cc-1c-skills` and
1C's PowerShell community). The 1,712 "wrong indent" errors are all in
existing files we did not author.

**Action for v1.1.1:** change `.editorconfig` to `indent_size = 2` for
PowerShell files, matching actual project style.

### 5. Auto-wrap script

`scripts/fix-line-lengths.py` was written and tested. It is **string-aware**
(uses Python's `tokenize` module to find safe split points) and rejects splits
that would put operators at the start of continuation lines. However, in
practice the script cannot reliably wrap the deeply nested expressions in
`tools/help-index-mcp/indexer.py` (e.g. nested `.replace("X", "Y").replace("Z",
"W")` chains across line 220+).

**Action for v1.1.1:** keep the script in `scripts/` as a reference, but
rely on `line-length = 125` cap in `pyproject.toml` rather than automatic
wrapping. The remaining 53 lines > 125 chars in 6 files are accepted as
historical.

## Files modified by pre-commit auto-fixes (already committed in 866667c)

Auto-fixed on first run:
- `tools/help-index-mcp/_test_pipeline.py` — trailing whitespace, line endings
- `tools/skills-bridge/{server.py,tools/*.py}` — line endings (CRLF → LF)
- `tools/help-index-mcp/{indexer,server,hbk_parser,toc_parser}.py` — line endings
- `tools/ibcmd-bridge/server.py` — line endings
- `tools/prompt-gallery/server.py` — line endings
- `docs/i18n/README_EN.md` — line endings
- `docs/marketing/COMPETITIVE_ANALYSIS_2026*.{md,txt}` — line endings
- `docs/legal/scans/reuse-2026-06-23.txt` — line endings

## v1.1.0 release-blocker checklist

Before tagging v1.1.0:

- [x] `pyproject.toml` line-length = 125, with E501/RUF001/RUF002/SIM108/UP031 ignored
- [x] `ruff` blocking for real issues (18 errors remain, all `F`/`B`/`UP` family)
- [x] `ruff-format` blocking, format matches Black style
- [x] `mixed-line-ending` blocking, all LF
- [x] `trailing-whitespace` blocking
- [x] `end-of-file-fixer` blocking
- [x] `reuse lint` blocking, 333/333 files compliant
- [x] `gitleaks` blocking, 0 leaks
- [x] `PSScriptAnalyzer` blocking (errors only)
- [x] `shellcheck` blocking (no .sh files yet)
- [x] `cargo clippy` + `cargo fmt` blocking for `tools/code-index-mcp`
- [ ] `codespell` blocking — needs per-directory excludes
- [ ] `markdownlint-cli2` blocking — needs per-file disable for inherited docs
- [ ] `editorconfig-checker` blocking — needs PS-file indent size adjustment

## Plan for v1.1.1 (next minor)

1. Update `.editorconfig`: PS files `indent_size = 2` (1 hour)
2. Update `.markdownlint.jsonc`: disable MD058 (blanks-around-tables),
   MD060 (table-column-style), MD040 (fenced-code-language) — these are
   too opinionated for our docs (1 hour)
3. Update `codespell` args with broader `**/cc-1c-skills/**` skip (15 min)
4. Run `pre-commit run --all-files` — expect near-zero failures
5. Promote the three to blocking stage
6. Tag v1.1.1

## Auto-wrap script reference

`scripts/fix-line-lengths.py` is left in the repo as a future-useful tool. It is
**not** wired into pre-commit because it requires careful human review of its
output (it can break unusual code patterns). The string-aware tokenizer-based
approach is sound; the failure mode is on deeply nested expressions where no
safe split point exists within `max_length`.

Run manually:
```bash
python scripts/fix-line-lengths.py --dry-run
python scripts/fix-line-lengths.py --max-length 100 tools/help-index-mcp/indexer.py
```
