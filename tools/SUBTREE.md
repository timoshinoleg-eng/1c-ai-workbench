# Vendored subtrees

This repository vendors two upstream projects as git subtrees. They are no
longer registered as `.gitmodules`; their content lives inside the
superproject's working tree at fixed paths.

## Layout

| Path | Upstream | Pinned tip | Last sync | License |
|---|---|---|---|---|
| `tools/cc-1c-skills`   | `https://github.com/Nikolay-Shirokov/cc-1c-skills.git`   | `3a7f1c17637b47fa08eabedd27660ae693f5f19c` (tag `w-2026-06-28`) | 2026-06-30 | MIT |
| `tools/code-index-mcp` | `https://github.com/Regsorm/code-index-mcp.git`           | `f9dd5daa2952d51fd27b50845beba5e90fe7c07e` (just past tag `v0.42.2`) | 2026-06-30 | MIT |

Original submodule gitlinks (pre-subtree migration) are recorded in
`tools/SUBTREE-ORIGINAL-SHAS.txt` for audit purposes.

## Why subtree, not submodule

- **Fresh-clone reproducibility**: `git clone <superproject>` brings both
  vendored projects in one step, with no `git submodule update --init` race
  and no submodule-pointer divergence. The reported-by-review
  `NOT_READY_FOR_PAID_PILOT` blocker (empty submodule working trees) is
  structurally impossible after this migration.
- **Atomic pinning**: a single commit on `main` pins both SHA tips. Reviewers
  see one diff; bisect is single-axis.
