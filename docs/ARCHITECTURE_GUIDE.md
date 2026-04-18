# Architecture Guide

A set of architectural rules and principles for building clean, maintainable software systems.
Based on Robert C. Martin's *Clean Architecture* (2017) and *Clean Code* (2008).

---

## Programming Paradigms as Constraints

Each paradigm removes a capability from the programmer — not adds one:

| Paradigm | Constraint | Benefit |
|----------|-----------|---------|
| **Structured** | No direct `goto` | Predictable control flow |
| **Object-Oriented** | No unconstrained indirect transfer of control | Dependency inversion mechanism |
| **Functional** | No assignment / mutable state | No race conditions, referential transparency |

Use all three. OOP is not a default — it is a tool for managing dependencies across boundaries.

---

## SOLID — Module Design

### SRP — Single Responsibility Principle
A module has one and only one reason to change.
It is responsible to one and only one actor.

> A class with two reasons to change is two classes waiting to be separated.

### OCP — Open/Closed Principle
Software entities should be open for extension but closed for modification.

- New behavior → new code
- Old behavior → unchanged code
- Achieved through abstraction: depend on interfaces, not implementations

### LSP — Liskov Substitution Principle
Subtypes must be substitutable for their base types without altering correctness.
A contract between caller and callee must be honoured by every implementation.

### ISP — Interface Segregation Principle
Do not depend on code you don't use.
Split fat interfaces into focused, narrow interfaces.
Callers import only the slice they need.

### DIP — Dependency Inversion Principle
High-level policy must not depend on low-level detail.
Both must depend on abstractions.
Abstractions must not depend on details — details depend on abstractions.

> All import arrows that cross architectural boundaries must point inward, toward high-level policy.

---

## Component Cohesion

### REP — Reuse/Release Equivalence Principle
The unit of reuse is the unit of release.
Group classes that are released together.

### CCP — Common Closure Principle
Classes that change for the same reason at the same time belong together.
Classes that change for different reasons belong apart.
(SRP applied to components — gather together what changes together)

### CRP — Common Reuse Principle
Do not force users of a component to depend on things they don't need.
(ISP applied to components)

---

## Component Coupling

### ADP — Acyclic Dependencies Principle
No cycles in the component dependency graph.
If a cycle exists, break it with a new component or dependency inversion.

### SDP — Stable Dependencies Principle
Depend in the direction of stability.
A component that is expected to change must not be depended on by a component that is hard to change.

**Stability metric**: I = Fan-out / (Fan-in + Fan-out)
- I = 0 → maximally stable (many dependents, no dependencies)
- I = 1 → maximally unstable (no dependents, many dependencies)

### SAP — Stable Abstractions Principle
A component should be as abstract as it is stable.
Stable components → abstract (interfaces, base classes)
Unstable components → concrete (implementations, details)

> The Main Sequence: components should sit near the line where abstractness equals stability.

---

## Clean Architecture

### The Dependency Rule

> Source code dependencies must point only inward, toward higher-level policies.

Nothing in an inner circle may know about anything in an outer circle.
This includes: function names, class names, variables, and data formats.

### Concentric Layers

```
┌──────────────────────────────────┐
│  Frameworks & Drivers (outer)    │
│  ┌────────────────────────────┐  │
│  │  Interface Adapters        │  │
│  │  ┌──────────────────────┐  │  │
│  │  │  Application / Use   │  │  │
│  │  │  Cases               │  │  │
│  │  │  ┌────────────────┐  │  │  │
│  │  │  │  Entities      │  │  │  │
│  │  │  │  (inner)       │  │  │  │
│  │  │  └────────────────┘  │  │  │
│  │  └──────────────────────┘  │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

| Layer | Contains | May import |
|-------|----------|-----------|
| Entities | Business rules, domain objects | Nothing from outer layers |
| Use Cases | Application logic, orchestration | Entities only |
| Interface Adapters | Controllers, presenters, gateways | Use Cases, Entities |
| Frameworks & Drivers | DB, UI, web, CLI | Anything |

### Separation of Layers and Use Cases

Decompose the system along two axes simultaneously:

**Horizontal layers** (technical concerns):
- UI / Delivery mechanism
- Application-specific business rules (use cases)
- Application-agnostic business rules (entities)
- Database / external interfaces

**Vertical slices** (business concerns):
- Each use case cuts through all horizontal layers
- A use case owns its slice end-to-end

Both axes are independent. A change in a use case should not require changes in unrelated use cases. A change in the delivery mechanism should not require changes in business rules.

### Crossing Boundaries

Data crossing a boundary must be in a form convenient for the inner layer.
Never pass framework objects (ORM models, HTTP request objects) into use cases.
Use simple data structures or domain objects.

---

## Key Patterns

### Humble Object Pattern
Separate testable behavior from untestable behavior.
Push all logic into a testable object; leave the untestable shell (UI, DB, I/O) humble — with minimal logic.

### Partial Boundaries
When a full architectural boundary is too expensive, use:
- Strategy pattern (dependency inversion without separate deployability)
- Facade pattern (simplified interface over a complex subsystem)
- One-dimensional boundary (only the interface, no reciprocal boundary)

Preserve the option to promote to a full boundary later.

### Event Sourcing
Store transactions (events), not current state.
Reconstruct state by replaying events.
Makes the application nearly side-effect-free and fully auditable.

---

## Development Practices

### TDD — Test-Driven Development

Cycle: **Red → Green → Refactor**

1. Write a failing test that specifies the desired behavior
2. Write the minimum code to make it pass
3. Refactor without breaking the test

TDD does not slow development — it eliminates the disorder caused by debugging untested code.
Tests are the specification, not the verification.

### Design Rules

- **Functions**: do one thing; one level of abstraction; no side effects; command-query separation
- **Names**: reveal intent; avoid disinformation; make meaningful distinctions
- **Comments**: explain *why*, never *what* — code should explain itself
- **Error handling**: use exceptions, not return codes; define exception classes by caller needs
- **Boundaries**: wrap third-party APIs so you can replace them without cascading changes

### Architecture as Decision Deferral

> A good architect maximizes the number of decisions not yet made.

The primary purpose of architecture is to keep options open:
- Defer the database decision
- Defer the framework decision
- Defer the UI decision

The longer these decisions can be deferred, the more information you have when you make them.

---

## Documentation Principles

### What to Document

- **Why** a decision was made, not what the code does
- Alternatives that were considered and rejected
- Invariants and contracts that are not visible in the code
- Boundaries and the direction of dependencies

### Architecture Decision Records (ADRs)

One short file per significant decision:
1. **Context** — what situation forced this decision
2. **Decision** — what was chosen
3. **Consequences** — what becomes easier and harder as a result

### Living Documentation

Documentation that drifts from reality is worse than no documentation.
Store architecture docs with the code.
Update docs as part of the definition of done.
Delete stale docs — a lie is more dangerous than silence.

---

## Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|-------------|---------|-----|
| **Big Ball of Mud** | No discernible structure; everything depends on everything | Apply layer discipline; enforce dependency rule |
| **Anemic Domain Model** | Domain objects with no behavior; all logic in services | Move behavior into entities |
| **Dependency on Framework** | Business logic imports from web/ORM framework | Invert dependency; framework adapts to domain |
| **Test-After Development** | Tests written to cover code, not specify behavior | Test-first; tests are the specification |
| **Premature Optimization** | Architecture shaped by performance guesses | Profile first; optimize second; never guess |
| **Screaming Framework** | Project structure reveals the framework, not the domain | Structure should scream the use cases |

---

> "The goal of software architecture is to minimize the human resources required to build and maintain the required system."
>
> — Robert C. Martin, *Clean Architecture*
