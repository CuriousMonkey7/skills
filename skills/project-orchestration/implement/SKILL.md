---
name: implement
description: >-
  Autonomously execute an explicitly approved GOALS.md issue graph by
  scheduling its ready frontier, delegating bounded implementation work,
  producing tested commits, invoking independent audits, remediating failures,
  and integrating accepted issues in dependency order. Use only after both the
  GOALS and issue graph approvals authorize implementation.
---

# Implement

Own autonomous delivery after the human-controlled planning gate. Do not reopen
accepted product decisions unless implementation reveals a genuine conflict or
requires new authority.

## Verify authorization

Read `GOALS.md` and all issue files. Start only when:

```text
GOALS approval: Approved
Issue graph approval: Approved
Implementation authorized: Yes
```

Require local issue sources and required GitHub mirrors to exist, unless the
user recorded an explicit waiver. If any condition is missing, stop without
delegating.

## Maintain one milestone objective

Keep exactly one active objective, equivalent to the active milestone outcome.
Use Goal-mode tools when available; otherwise record the objective and tool
limitation in `GOALS.md`. Do not complete or replace it until all milestone
issues are accepted and the milestone integration audit passes.

## Schedule the ready frontier

Repeatedly calculate open issues whose blockers are all `Accepted`.

- Run independent ready issues in parallel when worker capacity exists.
- Serialize issues with dependency edges or likely filesystem/interface
  conflicts even when the graph otherwise permits parallelism.
- Use isolated branches and worktrees for parallel code-changing workers when
  available. If isolation is unavailable, do not parallelize overlapping edits.
- Never let two workers claim the same issue.
- Keep blocked work idle; do not create substitute tasks merely to stay busy.

Update `GOALS.md`, local issue files, GitHub mirrors, and the optional dashboard
whenever the frontier or issue state changes.

## Dispatch bounded workers

Choose the worker surface deliberately:

- visible thread/worktree for work needing history, continuation, review, or
  repository isolation;
- subagent for bounded independent work that can finish in one context;
- local Computer Use thread for browser, desktop, credential, hardware, or
  device-dependent work.

Every brief must include:

- milestone objective, issue ID, and dependency context;
- expected outcome plus in-scope and out-of-scope boundaries;
- accepted decisions and constraints;
- files, systems, and public interfaces in scope;
- required checks and acceptance evidence;
- the pre-agreed TDD seam and red-green-refactor expectation, or the accepted
  reason and substitute feedback loop;
- branch/worktree and commit ownership;
- the required return format below.

Require workers to return only:

```text
Conclusions
- decisions, findings, and remaining risks

Changes
- files, systems, or behavior changed

Evidence
- tests, commands, artifacts, screenshots, or observations with results
- red-green-refactor evidence, or the accepted substitute and its result

Blockers
- unresolved items, or None
```

Do not paste worker transcripts into the coordinator thread.

## Produce a reviewable implementation commit

For each returned issue:

1. Verify the change is within scope and the required evidence actually ran.
2. Run the issue-level checks again when evidence is stale, incomplete, or not
   reproducible from the worker's surface.
3. Create one reviewable implementation commit when practical. The coordinator
   may commit shared-worktree changes; an isolated worker may commit its issue
   branch. Record the SHA either way.
4. Mark the issue `Committed`, not `Accepted`.
5. Invoke `$audit` in a fresh reviewer thread or subagent that did not implement
   the issue. Give it the fixed point, commit range, local issue, and GOALS.md.

Never merge an unaudited issue into the integration branch.

## Remediate audit failures

If the audit fails:

1. Record its actionable findings in the issue and `GOALS.md`.
2. Return the findings to the implementer or dispatch a bounded remediation
   worker.
3. Run the relevant checks.
4. Create a separate remediation commit and record its SHA.
5. Re-run `$audit` independently over the full issue commit range.

Repeat until the audit passes or a genuine blocker requires the user. Do not
weaken acceptance evidence after implementation starts without explicit user
approval and a recorded decision.

## Integrate accepted work

After an issue audit passes:

- mark the issue `Accepted` and synchronize its local and GitHub state;
- merge or integrate it in dependency order;
- run relevant integration checks after the merge;
- recalculate the frontier and dispatch newly unblocked issues.

When every issue in the active milestone is accepted, invoke `$audit` in
milestone mode against the integrated repository and milestone evidence. If it
passes, record the audit, complete the active objective, and activate the next
milestone. If it fails, remediate without advancing.

For the final milestone, also require every project-level acceptance item in
`GOALS.md`. Never infer completion from commits or worker confidence alone.

## Communicate state changes

Report only:

```markdown
What's done
- ...

What's next
- ...

Any blockers
- None.
```

Continue autonomously between state changes. Interrupt the user only for a
genuine blocker, a new permission boundary, or a decision that materially
changes the approved contract.
