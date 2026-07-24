# Release contract v1

This contract separates production signing from publication so that a GitHub
Release contains the exact binaries tested on a clean Windows host. No build is
allowed between verification and publication.

## Baseline

The implementation baseline is pull request 1 at commit `9e30b3e`, where all
eleven CI and CodeQL checks passed. The baseline includes:

- 64 Python tests and the full Rust suite;
- `code-index` 0.45.0 golden and incremental/full parity contracts;
- provider-free evidence evaluation with four passing cases;
- offline installer, upgrade, downgrade rejection, and uninstall acceptance.

This baseline is suitable for controlled read-only pilots. Public production
publication remains blocked until the signed-candidate path below is completed.

## Release version

Use `v0.10.0` for the first signed technical release unless the maintainer
separately approves the product commitments associated with `v1.0.0`. The
workflows accept any stable semantic version and do not make that product
decision automatically.

## Protected GitHub environments

Repository administrators must configure two environments:

1. `release-candidate`
   - stores `WINDOWS_SIGNING_CERT_PFX_BASE64`;
   - stores `WINDOWS_SIGNING_CERT_PFX_PASSWORD`;
   - restricts deployment to the protected `main` branch;
   - requires an approved maintainer before signing.
2. `production-release`
   - has required reviewers;
   - grants publication approval only after clean-Windows evidence has been
     reviewed.

The initial release path supports an exportable OV Authenticode PFX. An EV or
hardware-backed signer requires a separately reviewed Key Vault, cloud signing,
or self-hosted-runner integration.

## Phase A: build signed candidate

Run `.github/workflows/build-candidate.yml` manually with:

- `version`: semantic version without a `v` prefix;
- `commit_sha`: the full SHA currently at `origin/main`.

The workflow fails closed unless the requested commit is the current main head.
It then:

1. parses all PowerShell entrypoints;
2. builds and tests the Rust indexer;
3. runs the golden index and provider-free evaluation contracts;
4. creates a verified offline wheelhouse;
5. imports the environment-protected signing certificate;
6. builds and tests the signed installer;
7. emits one `release-candidate-*` artifact with:
   - the signed installer;
   - `bsl-indexer.exe`;
   - evaluation reports;
   - `candidate-manifest.json`;
   - `checksums.txt`.

Candidate artifacts expire after 14 days. The signing PFX is removed in an
`always()` cleanup step and is never included in an artifact.

## Phase B: clean-Windows verification

Download the candidate artifact from the successful workflow run and test it
on clean Windows 10 and Windows 11 x64 virtual machines without developer tools
or prior workbench installations.

Record:

- candidate workflow run ID, commit, version, and SHA-256;
- `signtool verify /pa /v` output and timestamp result;
- SmartScreen result with screenshot and text;
- install and launch result without an elevation prompt;
- `START_HERE.ps1` launch;
- `meta_info` and `form_info` responses on the committed demo fixture;
- uninstall result and preservation policy.

A new-certificate SmartScreen reputation warning is recorded and explicitly
accepted or rejected. It does not invalidate a cryptographically valid
Authenticode signature by itself.

Any functional, integrity, or signature failure requires a new commit, a fresh
review and CI run, and a new candidate. Candidate files must never be patched
in place.

## Phase C: publish verified candidate

Run `.github/workflows/publish-verified.yml` manually with:

- `candidate_run_id`: successful Phase A run;
- `tag`: stable semantic tag such as `v0.10.0`;
- `verification_record`: durable URL or repository reference to Phase B
  evidence.

The `production-release` environment approval is the human verification gate.
The workflow:

1. proves the run was produced by `build-candidate.yml` in this repository;
2. downloads its only non-expired release-candidate artifact;
3. validates the candidate manifest, every SHA-256, Authenticode signer, and
   RFC 3161 timestamp;
4. proves the frozen commit is in `main`;
5. creates an annotated tag without force-updating an existing tag;
6. publishes the exact downloaded files without compiling or signing again.

Existing GitHub Releases are never overwritten by this workflow.

## Parallel hardening

Hardening work uses a separate `hardening/*` branch. It must not be merged into
the frozen candidate commit after review. If a hardening change is required for
the release, it becomes a new release commit and restarts CI, review, signing,
and clean-Windows verification.

The first hardening slice is:

1. make mypy blocking in measured increments;
2. add pinned dependency audits and CycloneDX SBOM artifacts;
3. record coverage baselines before setting percentage targets;
4. classify production `unwrap()` and `expect()` calls, using `INVARIANT`
   comments only where a panic is demonstrably unreachable;
5. expand configured-boundary, corrupt-input, and MCP transport contract tests;
6. keep all `ibcmd` writes disabled in the public release.

Portable ZIP, performance budgets, status UX, log rotation, and broader
platform matrices remain post-publication reliability work. They do not block
the first signed installer.
