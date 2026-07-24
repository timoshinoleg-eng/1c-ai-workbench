# Repository governance

This document defines the minimum review and release controls for
`timoshinoleg-eng/1c-ai-workbench`.

## Roles

- `timoshinoleg-eng` is the repository administrator, pull request author, and
  release owner.
- `glebforewer-ui` is the approving collaborator for protected-branch and
  protected-environment gates.
- Codex performs the technical diff review, records findings on the pull
  request, and verifies that the reviewed commit is the commit approved by
  GitHub. Codex is not a GitHub identity and cannot satisfy a required approval
  by itself.

The pull request author must not provide the approval required for their own
change. The approving collaborator reviews the final head only after technical
findings are resolved and CI is complete.

## Protected main branch

Repository ruleset `protect-main` applies to `refs/heads/main` and:

- prohibits deletion and non-fast-forward updates;
- requires changes to arrive through a pull request;
- requires one approving review;
- dismisses approvals when new commits are pushed;
- requires all review threads to be resolved;
- requires the pull request branch to be tested with the latest `main`;
- has no administrator bypass.

The following check contexts are required exactly as written:

1. `Secret scan (gitleaks)`
2. `Analyze (python)`
3. `Python lint & format (ruff, black, mypy)`
4. `Rust build & test (bsl-indexer)`
5. `License compliance (REUSE)`
6. `Markdown lint`
7. `Pre-commit (all hooks)`
8. `PowerShell smoke checks`
9. `Windows installer offline, upgrade & uninstall`
10. `Cargo integration tests (full)`
11. `CodeQL`

Required contexts must be copied from successful GitHub check runs. Generic or
invented aliases must not be added because they would remain permanently
`Expected`.

## Review sequence

1. Push the complete change, including workflow and documentation updates.
2. Wait for every required check on that exact head SHA.
3. Record the Codex technical review on the pull request.
4. Resolve every review thread and push any fixes.
5. Repeat CI and technical review after the last push.
6. Mark the pull request ready for review.
7. Obtain approval from `glebforewer-ui` on the final head SHA.
8. Merge without bypassing the ruleset.
9. Verify required workflows on the resulting `main` merge commit.

An approval made before the final push is intentionally stale and does not
satisfy this process.

## Release controls

The release contract in `RELEASE_CONTRACT_V1.md` is mandatory:

- `release-candidate` protects signing credentials and candidate creation;
- `production-release` protects publication of an already verified candidate;
- publication consumes the exact candidate artifact and never rebuilds it;
- release tags are immutable and must not be deleted or force-updated;
- clean-Windows evidence must identify the candidate run, commit, version, and
  hashes.

The release owner and approving collaborator must review protected-environment
requests. Signing secrets are stored only as environment-scoped GitHub
secrets. They must not be placed in repository files, workflow inputs, comments,
logs, artifacts, or release notes.

## Emergency changes

An emergency does not permit force-pushing `main`, moving a release tag, or
publishing an unverified binary. Urgent fixes use a focused pull request and
the same required checks and approval. If GitHub itself is unavailable, the
release is delayed rather than recreated through an unreviewed path.

Any change to required checks, reviewer count, environment protection, signing
method, or tag policy is a governance change and must be reviewed through the
protected branch.
