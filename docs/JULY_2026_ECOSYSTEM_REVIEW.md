# July 2026 ecosystem review and delivery plan

Reviewed on 2026-07-18 against the live GitHub repositories and the current public `1c-ai-workbench` checkout.

## Outcome

The workbench should not bulk-vendor every active 1C project. The highest-value path is:

1. restore a green repository baseline and ship the recovered launcher;
2. upgrade the existing index core in isolation;
3. add a reproducible evaluation layer;
4. keep live-data and editor integrations external and disabled by default;
5. update the large skills vendor only after a scoped compatibility review.

This ordering preserves the product boundary: local exported files, read-only analysis, and a small Windows operator surface.

## Local cleanup result

The root of `C:\` previously contained 27 1C-related folders. Twenty-two disposable installer/package validations, clean clones, and `FINAL_TEST_1C*` generations were moved to the Windows Recycle Bin after comparison.

The retained roots are:

- `C:\1C` — launch, commercial, and security source documents;
- `C:\1c-ai-demo` — representative 1C dump used for acceptance;
- `C:\1c-ai-workbench` — dirty archive worktree with unrelated Git history;
- `C:\1c-ai-workbench-backup-mirror.git` — bare recovery mirror;
- `C:\1c-ai-workbench-local-backup-20260701-020006` — compact pre-sync source backup; its 7.86 GB generated Rust `target` cache was removed;
- `C:\cc-1c-skills-pr` — clean published branch with the shell-free subsystem validator fix.

The useful uncommitted files from `C:\FINAL_TEST_1C_FINAL` were migrated before cleanup. Most importantly, the 121-byte corrupted public `START_HERE.ps1` was replaced with the tested interactive launcher. The migrated launcher parses, accepts a clean exit, and the repository still passes 62 Python tests.

## July shortlist

### Upgrade in an isolated branch

#### code-index-mcp 0.45.0

- Current workbench binary: 0.42.2.
- Upstream delta: 29 commits and 36 files from the recorded vendor SHA.
- Important changes: tree-sitter BSL parser migration, bulk-index performance fixes, configuration-manifest reconciliation, and optional Docker/read-only HTTP deployment.
- Decision: highest-value core upgrade, but the parser change is breaking and requires golden-index comparison before merge.
- Sources: <https://github.com/Regsorm/code-index-mcp>, <https://github.com/Regsorm/code-index-mcp/releases/tag/v0.45.0>.

### Adapt methodology

#### PRISM 1.7.0

- MIT benchmark for LLM-generated BSL with reproducible scoring and real 1C execution.
- July CI and documentation builds are green.
- Decision: adapt the evaluation principles to provider-free workbench fixtures. Do not copy leaderboard results or make PRISM a runtime dependency.
- Sources: <https://github.com/genlab-1c/prism>, <https://github.com/genlab-1c/prism/releases/tag/v1.7.0>.

#### ИИкона YAxUnit suite

- MIT repository advertising 398 tests around agent loops, RAG, MCP, parsers, monitoring, and safety limits.
- Decision: use as a catalogue of test patterns. Tests are connector-specific and should not be copied directly.
- Source: <https://github.com/andromanpro/1c-ai-connector-tests>.

### Optional external pilots

#### MXL Merge Tool 0.1.0

- MIT semantic diff and three-way merge for `.mxl` files.
- Local isolated verification: 31 tests passed.
- Risk: project is one day old and has no upstream CI.
- Decision: keep reference-only until an optional adapter has workbench-owned contract tests. Never alter global Git configuration during default setup.
- Source: <https://github.com/alexiosus/mxl-merge-tool>.

#### 1C OData MCP 0.3.0

- MIT, maintained, structured tool output, read-only by default.
- Risk: the same server contains 34 opt-in write tools and handles live credentials.
- Decision: external integration profile only. Default workbench artifacts must not enable write mode, store credentials, or claim live-base safety without a separate review.
- Source: <https://github.com/evilbruce666/1c-odata-mcp>.

#### mcp-1c 1.11.2

- MIT free core, active releases, compact Go binary.
- Risk: live-base architecture and paid tiers overlap with workbench positioning.
- Decision: interoperability documentation only; do not vendor or depend on paid capabilities.
- Source: <https://github.com/feenlace/mcp-1c>.

### Reference-only tracks

- XBSL: strong MIT linter/LSP/MCP project, but it targets 1C:Element rather than Enterprise 8.3. <https://github.com/keyfire/xbsl>
- SonarQ in EDT: useful EDT 2026.1 diagnostic UX under EPL-2.0; keep it an external editor plugin. <https://github.com/Jimmo910/edt-sonarq-plugin>
- Landscape1C: continue using its discovery methodology and refresh source facts from the live data. <https://github.com/Oxotka/Landscape1C>
- EDT-MCP: AGPL-3.0 external option; do not vendor into the MIT default artifact. <https://github.com/DitriXNew/EDT-MCP>

## Vendor update boundaries

`cc-1c-skills` is 150 commits and about 300 changed files ahead of the recorded `w-2026-06-28` snapshot. A bulk sync is not acceptable. Update it by capability slice and run the skills-bridge contract suite after each slice. The July web-test work is valuable for a later write/test profile, but it does not belong in the default read-only artifact.

## Delivery plan

### Phase 0 — recover the release baseline

1. Commit the recovered launcher and documentation corrections to draft PR #1.
2. Repair all historically red CI jobs: gitleaks installation, Ruff/Black scope, Rust formatting, REUSE version/config, Markdown policy, pre-commit, and PowerShell preparation of the binary and virtual environment.
3. Require one fully green pull-request run and a green clean-install E2E before any vendor sync. Three consecutive green scheduled runs become the stability target after merge.

Acceptance:

- `START_HERE.ps1` parses and exits cleanly from a fresh checkout and installed artifact;
- 62 Python tests pass;
- strict installed-copy E2E has no failures or warnings;
- every required GitHub check is green on the exact head SHA.

### Phase 1 — code-index-mcp 0.45.0

1. Sync the vendor in a separate branch while retaining attribution and local patch boundaries.
2. Rebuild `bsl-indexer.exe` from the pinned upstream commit.
3. Index the same 350-file dump with 0.42.2 and 0.45.0.
4. Compare object counts, functions, calls, event subscriptions, register writers, search results, index time, and peak memory.
5. Reject the upgrade on missing evidence, data loss, new write paths, or an unexplained result drift.

Acceptance:

- all existing CLI and MCP contracts pass;
- golden query results are equal or intentionally improved with documented deltas;
- index time and memory do not regress by more than 15 percent without an approved reason;
- the installer contains the rebuilt binary with a pinned SHA-256.

### Phase 2 — reproducible evaluation

1. Add provider-free fixtures for metadata navigation, call-graph evidence, and answer citation quality.
2. Record deterministic JSON results and a human-readable summary.
3. Add an optional provider evaluation profile with an explicit budget and no default network calls.

Acceptance:

- the fixture run is deterministic on a clean machine;
- no API key is required for the default evaluation;
- results include evidence paths and cannot pass on empty output.

### Phase 3 — optional integrations

1. Define a common external-pack contract: disabled by default, separate install instructions, explicit data boundary, smoke command, license, and removal path.
2. Pilot the MXL merge tool without global Git mutations.
3. Pilot OData with a disposable read-only user and no write tools exposed.
4. Document mcp-1c interoperability without bundling it.

Acceptance:

- default setup and installer remain unchanged in network and live-data behavior;
- disabling or removing an external pack restores the original workbench state;
- no secret is written to Git-tracked files or logs.

### Phase 4 — selective skills refresh

1. Group the 150 upstream commits by read-only metadata, MXL, support guard, web-test, and write/build capabilities.
2. Import only a reviewed slice at a time.
3. Preserve the local shell-free validator fix or drop it only after the upstream implementation is proven equivalent.

Acceptance:

- all skills-bridge contract tests pass after every slice;
- default artifacts contain no newly enabled write or browser-control path;
- vendor provenance and license metadata identify the exact upstream commit.

## Independent Kimi review

Kimi independently agreed with the ordering: green baseline first, isolated `code-index-mcp` upgrade second, evaluation third, external packs later. Kimi classified the 150-commit `cc-1c-skills` bulk update as too aggressive and supported capability-sliced updates with bridge contract tests.
