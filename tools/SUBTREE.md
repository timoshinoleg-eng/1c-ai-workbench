# Vendored subtrees

This repository vendors two upstream projects as git subtrees. They are no
longer registered as `.gitmodules`; their content lives inside the
superproject's working tree at fixed paths.

## Layout

| Path | Upstream | Pinned tip | Last sync | License |
| --- | --- | --- | --- | --- |
| `tools/cc-1c-skills` | `https://github.com/Nikolay-Shirokov/cc-1c-skills.git` | `3a7f1c17637b47fa08eabedd27660ae693f5f19c` (tag `w-2026-06-28`) | 2026-06-30 | MIT |
| `tools/code-index-mcp` | `https://github.com/Regsorm/code-index-mcp.git` | `a0869e71767207aafa18e9d6c6abaddfb0555589` (tag `v0.45.0`) | 2026-07-18 | MIT |

Original submodule gitlinks (pre-subtree migration) are recorded in
`tools/SUBTREE-ORIGINAL-SHAS.txt` for audit purposes.

The historical conversion did not retain `git subtree` split metadata. Vendor
updates therefore use an audited upstream archive at the pinned commit, followed
by the documented local hardening patch set and a full source diff. The exact
upstream commit remains the provenance boundary even though `git subtree pull`
cannot discover the original add commit automatically.

## Why subtree, not submodule

- **Fresh-clone reproducibility**: `git clone <superproject>` brings both
  vendored projects in one step, with no `git submodule update --init` race
  and no submodule-pointer divergence. The reported-by-review
  `NOT_READY_FOR_PAID_PILOT` blocker (empty submodule working trees) is
  structurally impossible after this migration.
- **Atomic pinning**: a single commit on `main` pins both SHA tips. Reviewers
  see one diff; bisect is single-axis.
