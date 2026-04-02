# bug-investigator

Use when:
- The task is to reproduce, isolate, and explain a failure or regression.
- Logs, stack traces, validation failures, or data-quality issues need diagnosis.

Do not use when:
- The change is a straightforward new feature with no reported breakage.
- The task is mainly documentation or release writing.

Instructions:
1. Capture the symptom from the current tree, command output, test failure, or log source.
2. Trace inward from entrypoint to application logic to storage or external boundary.
3. Prefer a small reproduction: targeted `pytest`, a CLI help path, or the narrowest script that matches the issue.
4. State root cause, impacted path, and the smallest safe fix.
5. If the repo lacks a reproducible path, leave a `TODO` naming the exact missing input.

Optional delegation:
- One path can inspect runtime entrypoints while another inspects tests or schema ownership.
