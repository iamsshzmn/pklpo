---
name: ai-skill-practices
description: Applies AI-world best practices to author and improve skills: clear triggers, concise instructions, structured outputs, and prompt-engineering principles. Use when writing or refining skills, agent instructions, or Cursor rules.
---

# AI-World Practices for Good Skills

Best practices from prompt engineering and agent design for writing skills that work reliably with AI assistants.

## When to Use This Skill

- Writing or editing a new skill (SKILL.md, rules, agent prompts)
- Improving an existing skill (clarity, discoverability, token efficiency)
- Designing instructions for agents or tools
- Reviewing skill quality before committing

---

## 1. Clear Triggers (Discoverability)

The agent decides when to apply a skill from its **description**. Make that decision easy.

### Do

- **WHAT + WHEN**: Describe both capability and trigger scenarios.
- **Trigger terms**: Include exact phrases users or context might use.
- **Third person**: Description is injected into system context; write as "Does X when Y" not "I can help you with X."

```yaml
# Good
description: Generate conventional commit messages by analyzing git diffs. Use when the user asks for a commit message, reviews staged changes, or mentions conventional commits.

# Good
description: Review code for quality and security following team standards. Use when reviewing pull requests, code changes, or when the user asks for a code review.
```

### Avoid

- Vague scope: "Helps with code" → be specific.
- First/second person in description: "You can use this to..." or "I help with..."
- Missing WHEN: say when the skill should fire.

---

## 2. Concise Instructions (Token Economy)

Context is shared; every token competes. Assume the model is capable—only add what it wouldn’t infer.

### Do

- Lead with the rule or pattern; cut long intros.
- Prefer bullets and short steps over paragraphs.
- Use code blocks for formats and templates, not prose.
- Link to reference files for depth; keep SKILL.md under ~500 lines.

### Avoid

- Explaining basics the model already knows.
- Repeating the same idea in multiple ways.
- Long "why" sections unless they change behavior.

**Test**: For each paragraph, ask "If I remove this, would behavior change?" If not, trim or move to reference.

---

## 3. Structured Outputs (Predictable Quality)

When the skill produces artifacts (reports, commits, reviews), define the shape.

### Do

- **Templates**: Give a markdown or structure the agent must follow.
- **Sections**: Required sections and order (e.g. Summary → Findings → Recommendations).
- **Examples**: One or two concrete good outputs, not abstract advice.
- **Formats**: Explicit format for lists, headers, severity levels.

```markdown
## Report structure

Use this template:

# [Title]
## Summary
[One short paragraph]
## Findings
- **Finding 1**: [description]
- **Finding 2**: [description]
## Recommendations
1. [Actionable item]
2. [Actionable item]
```

### Avoid

- "Write a good report" without structure.
- Many alternative formats in one skill (pick one default, document exceptions).

---

## 4. Progressive Disclosure

Put only what’s needed for the main workflow in SKILL.md. Push detail to one level of references.

### Do

- **SKILL.md**: Quick start, checklist, main workflow, one or two examples.
- **reference.md / examples.md**: Deeper API, edge cases, more examples.
- **Single-level links**: SKILL.md → reference.md. No long chains (A → B → C).

### Avoid

- Putting everything in one huge SKILL.md.
- Deep reference chains (hard to load and maintain).
- Hiding critical steps inside "see reference" without a one-line summary in SKILL.md.

---

## 5. Degrees of Freedom

Match rigidity to how fragile the task is.

| Level   | When to use                    | Example                          |
|---------|--------------------------------|----------------------------------|
| **High**  | Many valid approaches          | "Review for security and style"  |
| **Medium** | Preferred pattern, some variation | "Use this report template"     |
| **Low**   | Consistency is critical        | "Run this exact command sequence" |

- **High**: Short principles, few hard rules.
- **Medium**: Template + 1–2 examples + "prefer X; if Y then Z."
- **Low**: Step-by-step, exact commands or scripts, minimal branching.

---

## 6. Examples Over Abstraction

Concrete examples beat abstract descriptions.

### Do

- **Input → Output**: Show a sample input and the expected output.
- **Good vs bad**: One "do this" and one "not this" when the distinction is subtle.
- **Real-ish data**: Names and values that look like real use (e.g. real file types, realistic commit messages).

```markdown
## Commit message format

**Example**
Input: Added JWT auth and login endpoint
Output:
feat(auth): add JWT authentication and login endpoint
```

### Avoid

- Only describing the format in words.
- Purely abstract "e.g. something like this" with no concrete line.

---

## 7. Constraints and Guardrails

Spell out what must always or never happen.

### Do

- **Always**: "Always validate input." "Always use parameterized queries."
- **Never**: "Never hardcode secrets." "Never expose stack traces to the client."
- **Defaults**: "Default to dry-run unless --apply is given."
- **Limits**: Max length, allowed values, timeouts where relevant.

Put the strictest constraints near the top or in a "Critical" subsection.

### Avoid

- Burying safety rules in the middle of long text.
- Vague "be careful with X" without a concrete rule.

---

## 8. Anti-Patterns

| Anti-pattern | Fix |
|--------------|-----|
| **Vague skill name** | Use specific names: `conventional-commits`, `security-review`, not `helper` or `utils`. |
| **Too many options** | One default path; document one clear alternative if needed. |
| **Time-sensitive wording** | "Use API v2" in main text; put "Before 2025 we used v1" in a deprecated section. |
| **Mixed terminology** | Pick one term (e.g. "endpoint" or "route") and stick to it. |
| **Windows-style paths in skills** | Use forward slashes: `scripts/helper.py`, not `scripts\helper.py`. |
| **Scripts without purpose** | State whether the agent should run the script or only read it; document required env/tools. |

---

## 9. Quality Checklist

Before considering a skill done:

### Discoverability
- [ ] Description states WHAT the skill does and WHEN it applies.
- [ ] Description is in third person and under ~1024 characters.
- [ ] Name is specific (lowercase, hyphens, ≤64 chars).

### Instructions
- [ ] Main workflow is in SKILL.md; depth is in linked references (one level).
- [ ] No long explanations of basics; every paragraph affects behavior or clarity.
- [ ] SKILL.md is under ~500 lines.

### Outputs
- [ ] If the skill produces artifacts, a template or structure is defined.
- [ ] At least one concrete input/output example exists.
- [ ] Critical "always/never" and limits are explicit and easy to find.

### Consistency
- [ ] One main approach; alternatives are clearly marked.
- [ ] Terminology is consistent.
- [ ] No time-sensitive "current" facts without a deprecated section.

---

## Summary

Good skills from an "AI world" perspective are **easy to trigger** (clear description + WHEN), **cheap in context** (concise, progressive disclosure), and **predictable in effect** (structure, examples, constraints). Apply this skill when creating or refining any skill, rule, or agent instruction set.
