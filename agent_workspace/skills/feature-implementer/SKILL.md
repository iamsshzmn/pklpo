# feature-implementer

Use when:
- The task needs production code changes in existing modules, commands, migrations, or docs.
- The scope is clear enough to edit current files directly.

Do not use when:
- The task is only exploratory.
- The main need is root-cause analysis without a confirmed fix.

Instructions:
1. Read the owning module and the nearest tests before editing.
2. Follow the current layering already used in that area, especially `domain`, `application`, `infrastructure`, and `cli` splits.
3. Keep changes minimal, consistent with existing naming, and explicit about any new assumptions.
4. Run the smallest useful validation for the touched area before broad checks.
5. Update nearby docs only when behavior, commands, or operator expectations changed.

Optional delegation:
- Safe split points are docs-only updates versus code changes, or disjoint modules with different owners.
