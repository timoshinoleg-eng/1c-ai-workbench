"""Top-level pytest configuration for 1c-ai-workbench.

Vendored subtrees under ``tools/`` ship with their own test scripts that
happen to match pytest's collection defaults (``test_*.py`` files plus
classes starting with ``Test``). Many of those scripts are E2E harnesses
that use ``TestCase`` as a plain dataclass name, which would otherwise
trigger ``PytestCollectionWarning`` and abort collection.

Skip those paths explicitly. Real test code for the workbench lives under
``tests/`` and is unaffected.
"""

from __future__ import annotations

collect_ignore_glob = [
    "tools/code-index-mcp/scripts/test_*.py",
    "tools/code-index-mcp/tests/**/*.py",
    "tools/cc-1c-skills/scripts/**",
    "tools/cc-1c-skills/tests/skills/**",
    "tools/cc-1c-skills/tests/web-test/**",
]
