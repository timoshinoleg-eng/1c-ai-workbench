# Production readiness — 2026-07-18

## Decision

- **GO:** local demo, internal use, and a controlled read-only customer pilot.
- **NO-GO:** broad public production publication of the Windows installer.

The remaining public-release blockers are external and fail-closed: a real
production Authenticode certificate is not available, and the final immutable
release tag/SHA-256 pin cannot be written until the signed release asset exists.

## Verified release candidate

- Vendored `code-index-mcp` is pinned to upstream tag `v0.45.0`, commit
  `a0869e71767207aafa18e9d6c6abaddfb0555589`.
- The full Rust suite passes with no failed tests; one doctest is intentionally
  ignored. Local compilation uses `CARGO_BUILD_JOBS=1` because the parallel
  debug build exhausted this Windows host's pagefile (`os error 1455`). GitHub
  CI remains the required clean-host parallel confirmation.
- Repository Python tests: 64 passed.
- Pre-commit, Gitleaks, PowerShell analysis, JSON/YAML/TOML validation, and REUSE
  pass; REUSE covers 2824/2824 files.
- Golden code-index contract passes exact 0.45.0 version, fixed stats and query,
  manifest reconciliation, and incremental/full parity across nine semantic
  tables.
- Provider-free PRISM-like evaluation passes 4/4 with source-line evidence for
  symbol navigation, body evidence, call graph, and metadata manifest lookup.
- Two unsigned local installer candidates passed install, fully offline Python
  setup, `code-index 0.45.0` payload assertion, `0.10.0 → 0.10.1` upgrade,
  user-data preservation, downgrade rejection, and uninstall policy.

## 0.42.2 → 0.45.0 pilot evidence

| Metric | 0.42.2 | 0.45.0 | Delta |
|---|---:|---:|---:|
| Full index time | 2216 ms | 2033 ms | -8.3% |
| Full peak memory | 24.1 MB | 24.4 MB | +1.2% |
| Incremental time | 1524 ms | 1468 ms | -3.7% |
| Incremental peak memory | 24.6 MB | 24.3 MB | -1.2% |

Function, class, and variable counts are preserved. The call count reduction
from 1664 to 1565 removes 99 false constructor calls. `ConfigDumpInfo.xml` is
intentionally represented in `config_manifest` instead of generic text search.
Exact procedure lookup and BSL body evidence remain available.

## Kimi adversarial review disposition

Kimi classified unsigned publication, stale artifact pins, unfinished gates,
and unverified parallel Windows testing as release blockers. The stale pin was
removed: `setup.ps1` now requires an explicit release tag plus SHA-256 and also
checks the binary version. Installer and evaluation gates are complete. The
real certificate and final release pin remain correctly open; GitHub CI must
confirm the parallel clean-runner path.

## External integrations

MXL merge, 1C OData MCP, and mcp-1c interoperability are catalogued but remain
disabled, unbundled, credential-isolated, rootless, and write-disabled. They do
not change default installer, network, or live-data behavior. Live pilots need
separate disposable environments and are not production dependencies.

## Remaining production plan

1. Obtain the approved production Authenticode certificate and configure the
   protected `release-candidate` environment.
2. Merge only after CI and CodeQL are green on the same reviewed head SHA, then
   freeze the resulting `main` commit.
3. Run `build-candidate.yml` for that exact commit. It signs, tests, and uploads
   one immutable candidate artifact without creating a tag or GitHub Release.
4. Validate that exact artifact on clean Windows 10 and Windows 11 hosts and
   record the signer chain, RFC 3161 timestamp, SmartScreen behavior, functional
   smoke, and uninstall result.
5. Approve `publish-verified.yml` through the protected `production-release`
   environment. It verifies provenance and checksums, creates the immutable tag,
   and publishes the downloaded candidate without rebuilding it.
6. Write the published tag/SHA pin back to `setup.ps1` on the next development
   commit and rerun CI; never move the published tag.
7. After public release, run MXL and OData pilots only in disposable isolated
   environments; promote an adapter only with its own contract and rollback.
8. Refresh `cc-1c-skills` in reviewed capability slices, never as an unreviewed
   150-commit bulk import.

Public production readiness is achieved only after steps 1–5 pass. Until then,
the draft pull request must remain draft and no unsigned installer should be
published as production.
