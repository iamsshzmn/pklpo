# release-notes-writer

Use when:
- The task is to summarize shipped changes for engineers or operators.
- You need a concise handoff for CLI, migrations, DAG behavior, or validation impact.

Do not use when:
- The work is still unstable or unverified.
- The task is code implementation or investigation.

Instructions:
1. Summarize only changes visible in the current working tree.
2. Group notes by operator impact: CLI, data model or migrations, DAGs, validations, docs.
3. Include only confirmed commands and checks.
4. Call out manual follow-up steps and unresolved `TODO`s.
5. Keep it brief and specific; no generic release boilerplate.
