---
name: orchestrate-projects
description: >-
  Autonomously coordinate substantial, multi-milestone projects through a
  human-controlled shaping pipeline and an evidence-gated delivery pipeline.
  Use when Codex should drive a project through shared understanding, an
  approved GOALS.md contract, dependency-linked local and GitHub issues,
  parallel or sequential worker execution, tested commits, independent audits,
  remediation, and final acceptance. Never delegate before both planning gates
  explicitly authorize implementation.
---

# Orchestrate Projects

Act as the project coordinator and state-machine owner. Keep this thread focused
on decisions, stage transitions, durable state, and outcomes. Use the sibling
stage skills for the work inside each stage rather than duplicating their
instructions here.

## Resume before routing

1. Read project instructions and check for `GOALS.md`.
2. If it exists, resume from its planning gate, current objective, issue graph,
   ready frontier, evidence, and audit state.
3. If a legacy `GOALS.md` lacks the planning gate, preserve its recorded work
   but do not infer implementation authorization. Use `$to-goals` to migrate it
   and obtain explicit approval before delegating.
4. Keep `GOALS.md` authoritative for project contract, dependencies, state,
   evidence, decisions, and audit results.

## Route the project stages

### 1. Shared understanding

When no accepted project contract exists, read and follow
[`$grill-me`](../grill-me/SKILL.md).

- Keep discovery user-led and conversational.
- Do not create implementation artifacts or delegate workers.
- Research or prototype only when the user explicitly authorizes it for a
  named discovery question, and do it in this coordinator thread.
- Wait for explicit acceptance of the shared-understanding summary.

### 2. Project contract and roadmap

After discovery is accepted, read and follow
[`$to-goals`](../to-goals/SKILL.md).

- Create or update the root `GOALS.md` from the canonical template owned by
  that skill.
- Do not repeat discovery.
- Wait for explicit GOALS approval.
- Do not delegate, activate implementation, or create execution issues yet.

### 3. Executable issue graph

After GOALS approval, read and follow
[`$to-issues`](../to-issues/SKILL.md).

- Create authoritative local vertical-slice issue files.
- Mirror an approved parent/child and blocking graph to GitHub when in scope.
- Record dependencies and the ready frontier in `GOALS.md`.
- Wait for explicit issue-graph approval.
- Do not delegate or implement in this stage.

### 4. Autonomous implementation

When `GOALS.md` records both approvals and `Implementation authorized: Yes`,
read and follow [`$implement`](../implement/SKILL.md).

This is the first stage that may delegate. Continue autonomously through ready
frontier scheduling, parallel or sequential execution, tests, implementation
commits, independent `$audit` reviews, remediation commits, integration, and
milestone transitions. Ask the user only for genuine blockers, new authority,
or decisions that materially change the accepted contract.

### 5. Independent evidence gates

For every committed issue, every integrated milestone, and final project
completion, require a fresh reviewer to read and follow
[`$audit`](../audit/SKILL.md). The implementer cannot audit its own work. A
failed audit returns to `$implement`; it never advances project state.

## Enforce the planning boundary

Before implementation authorization, never:

- spawn implementation, investigation, testing, review, or remediation
  workers;
- create implementation branches or commits;
- activate a Goal-mode implementation objective;
- treat silence, automatic continuation, or generic autonomy as approval.

After authorization, autonomy is the default. Do not ask for routine permission
between issues, commits, audits, remediation, or unblocked milestones.

## Preserve authoritative state

- `GOALS.md` owns project contract, milestone state, dependency state, ready
  frontier, evidence, decisions, blockers, and audits.
- Local issue files own issue scope and acceptance criteria.
- GitHub issues mirror the local parent/child execution queue.
- Apply scope changes locally first, record them in `GOALS.md`, then synchronize
  GitHub.
- Keep exactly one active objective: the current milestone outcome.
- Never maintain a second roadmap or copy mutable state into a shadow brief.

## Maintain the dashboard

When the project has at least three milestones or implementation uses at least
two concurrent workers, copy
[the dashboard template](assets/progress-dashboard.template.html) to the
project root as `progress-dashboard.html`.

Treat it as a projection of `GOALS.md`. Synchronize it after changes to the
active objective, ready frontier, issue or milestone state, workers, blockers,
evidence, or audits. Never use the dashboard as an input source.

## Communicate project state

When durable state changes, report only:

```markdown
What's done
- ...

What's next
- ...

Any blockers
- None.
```

Outside state changes, continue the discovery or decision conversation
normally. Do not include worker transcripts or tool narration.

## Completion rule

Declare the project complete only when:

- every required issue is accepted;
- every milestone integration audit passes;
- all project-level acceptance evidence is present;
- the final independent project audit passes;
- `GOALS.md`, local issues, GitHub mirrors, and the dashboard agree;
- the active objective is completed only after those facts are recorded.
