# How to Plan (Agent-Oriented Guide)

## Purpose

This document defines how to structure, execute, and track work using agents and reusable skills. It is designed to be:

- Human-readable
- Agent-executable
- Minimal in tokens

---

## Core Principles

- Break work into small, verifiable steps
- One task = one clear outcome
- Always define acceptance criteria
- Prefer reuse (skills) over re-writing logic
- Track progress explicitly
- Avoid ambiguity

---

## Plan Structure

Each plan must follow this structure:

```md
# Plan: <name>

## Goal
<clear final outcome>

## Constraints
<limits, assumptions, risks>

## Stages
- Stage 1: <name>
- Stage 2: <name>

## Tasks
### Task: <name>
- owner: <agent>
- skill: <skill_name>
- status: planned | in_progress | done | blocked
- input: <what is needed>
- output: <expected result>
- acceptance: <how to verify>

## Progress
- total_tasks: N
- done: X
- progress: X/N

## Notes
<any important context>
```

---

## Stages (Recommended)

Use standard stages when possible:

1. Research
2. Design
3. Implementation
4. Validation
5. Optimization

Stages can be skipped or merged if not needed.

---

## Task Design Rules

Each task must:

- Be atomic (cannot be split further)
- Be testable
- Have clear input/output
- Be assignable to one agent

Bad example:
- "Fix system"

Good example:
- "Implement SQL gap detection query"

---

## Agents

Recommended base agents:

- repo-explorer → analyze codebase
- feature-implementer → write code
- test-runner → validate behavior
- bug-investigator → debug issues
- refactor-reviewer → improve structure

Optional:
- orchestrator → controls flow
- reviewer → validates final result

Rule:
- One agent per task
- No mixed responsibilities

---

## Skills

Skills are reusable execution units.

Examples:
- write_sql_query
- implement_airflow_dag
- validate_data_consistency

Rules:
- Skills must be reusable
- Skills must be specific
- Store skills in separate files if possible

---

## Progress Tracking

Use simple status model:

- planned
- in_progress
- done
- blocked

Optional:
- progress %
- timestamps

Example:

```md
- [x] Task A
- [ ] Task B
```

---

## Acceptance Criteria

Each task must define:

- measurable result
- validation method

Examples:
- "Query returns correct rows"
- "No missing timestamps"

---

## Dependencies

Explicitly define dependencies:

```md
Task B depends on Task A
```

Avoid hidden dependencies.

---

## Error Handling

For each task define:

- retry strategy
- fallback (if possible)
- failure condition

Example:

```md
on_fail: retry 3 times
on_fail_final: mark blocked
```

---

## Quality Control

Add a validation step:

- correctness
- completeness
- consistency

Optional reviewer agent.

---

## Optimization

After implementation:

- remove duplication
- simplify logic
- reduce cost (tokens, compute)

---

## Token Efficiency Guidelines

- Use short task descriptions
- Avoid repeating context
- Reference instead of rewriting
- Use skills instead of inline logic
- Avoid large code blocks unless required

---

## What is Often Missed

- acceptance criteria
- dependencies
- rollback plan
- validation step
- clear outputs

---

## Naming

Recommended file names:

- how-to-plan.md (standard)
- planning-guide.md (alternative)
- execution-plan.md (for specific tasks)

Preferred: **how-to-plan.md**

---

## Minimal Example

```md
# Plan: Gap Detection

## Goal
Detect missing OHLCV candles

## Tasks

### Task: Build SQL query
- owner: feature-implementer
- skill: write_sql_query
- status: planned
- output: gap detection query
- acceptance: query finds gaps correctly
```

## Observability

Every production-relevant task must define observability before it is marked done.

Required output:

- metrics
- structured logs
- correlation/run context
- dashboard expectation
- alert expectation
- validation method

### Task: Add observability contract

- owner: feature-implementer
- skill: implement_observability_contract
- status: planned
- input: module/service/DAG behavior
- output: telemetry contract
- acceptance:

  - metrics expose status, duration, errors, processed count
  - logs are searchable by run_id/correlation_id
  - failures include stable error_type and reason
  - dashboard/alert expectations are documented
  - no secrets or high-cardinality labels are emitted

---

## End
