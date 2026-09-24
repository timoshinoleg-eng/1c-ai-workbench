# GitVerse + Cloud.ru CI pilot

This document describes the first non-destructive integration step between
1C AI Workbench, GitVerse CI/CD and Cloud.ru.

## Target Cloud.ru project

Project ID:

```text
9dcd962b-a943-4762-9b53-51ad3da59415
```

The project ID is an identifier, not a credential. No Cloud.ru access keys,
passwords or tokens are committed to the repository.

## Stage 1: validation-only CI

The workflow at `.gitverse/workflows/cloudru-ci.yml`:

1. checks out the repository;
2. configures Python 3.10;
3. installs project dependencies;
4. runs the Python test suite;
5. validates that the configured Cloud.ru project ID is a UUID;
6. records the intended Cloud.ru target without creating or changing resources.

This stage is intentionally safe for the first GitVerse mirror/import.

## Stage 2: Artifact Registry

Before enabling image publishing, create or select a Cloud.ru Artifact Registry
and add the following values as protected GitVerse CI/CD secrets:

- `CLOUD_RU_REGISTRY`;
- `CLOUD_RU_USERNAME`;
- `CLOUD_RU_PASSWORD`.

The Cloud.ru project identifier may remain in the workflow as a non-secret
configuration value, or be moved to the `CLOUD_RU_PROJECT_ID` secret for
consistency with Cloud.ru/GitVerse deployment examples.

Never commit access keys to YAML, README files, scripts or source code.

## Stage 3: Container Apps

Container Apps deployment stays manual until all of the following are true:

- the Linux container boundary is explicitly defined;
- a dedicated Dockerfile exists for the cloud-facing component;
- no customer 1C dump, generated index or proprietary data is included;
- the image is successfully published to Artifact Registry;
- resource limits and scale-to-zero behavior are reviewed;
- the deployment workflow is reviewed separately.

The local Windows workbench remains the system of record for read-only
inspection of customer 1C exports. Cloud components should expose only the
minimum service surface required by the pilot.

## Candidate cloud split

A safe target architecture is:

```text
Customer workstation / Windows
  1C XML dump
      |
      v
  local Workbench + local indexes
      |
      | controlled MCP/API boundary
      v
Cloud.ru
  optional stateless pilot services
  Artifact Registry
  Container Apps
  AI Agents / MCP integration
```

This preserves the project's privacy-first design while allowing Cloud.ru to be
used for CI/CD, demos and B2B pilot infrastructure.

## GitVerse setup

GitVerse detects workflows under `.gitverse/workflows/`.

After importing/mirroring the repository:

1. enable CI/CD in repository settings if it is disabled;
2. push the repository with `.gitverse/workflows/cloudru-ci.yml`;
3. verify the first CI run;
4. only after a green validation run, configure Cloud.ru credentials as
   protected secrets;
5. add Artifact Registry publishing as a separate reviewed change.

## Security rule

The initial workflow must not deploy, delete or mutate Cloud.ru resources.
Any future CD job must be explicit, reviewable and manual-first.
