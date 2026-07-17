---
name: to-issues
description: >-
  Decompose an approved GOALS.md into dependency-linked, vertical-slice
  execution issues, store their authoritative scope locally, mirror them as a
  GitHub parent and child issue graph, and obtain explicit approval for
  autonomous implementation. Use after GOALS approval and before any worker is
  delegated or implementation begins.
---

# To Issues

Turn the accepted roadmap into an executable dependency graph without starting
the work.

## Check the gate

Require all of the following:

- `GOALS.md` exists and is authoritative;
- `GOALS approval` is `Approved`;
- milestones, boundaries, and evidence requirements are present;
- `Implementation authorized` is still `No`.

If a milestone is not understood well enough to decompose, return the missing
decision to the coordinator. Do not delegate an investigation to fill the gap.

## Create vertical-slice issues

For each implementable milestone:

1. Break the work into narrow but complete tracer-bullet slices.
2. Make every issue independently testable, inspectable, or demoable.
3. Size each issue to fit one fresh worker context.
4. Give it a stable ID such as `M1-I01`.
5. Record only genuine blocking edges and verify the graph is acyclic.
6. Identify likely file or interface overlap. Serialize issues whose changes
   would conflict even if their product behavior is otherwise independent.
7. Use horizontal or wide-refactor issues only for true prerequisites that
   cannot remain green as vertical slices; explain the exception.

Each issue must state outcome, scope, non-scope, dependencies, relevant
decisions, interfaces in scope, required evidence, and its TDD seam or named
substitute feedback loop.

## Draft locally first

Create one authoritative file per issue under the configured project issue
directory, defaulting to `project/issues/`, using
[the issue template](assets/ISSUE.template.md). Update the `GOALS.md` issue
graph and ready frontier.

Present the proposed graph to the user. Ask whether granularity, blocking
edges, and parallel groups are correct. Iterate until explicitly approved.

## Mirror the approved graph to GitHub

When GitHub issue tracking is in scope and connected:

1. Create one GitHub parent issue containing the stable `GOALS.md` summary and
   a repository link to the file. Do not copy mutable project state into the
   parent body.
2. Create one child issue for every local issue file in dependency order.
3. Use native parent/child and blocking relationships when available;
   otherwise encode the links in the issue bodies.
4. Put the local source path in each GitHub issue and its GitHub URL in the
   local file and `GOALS.md`.

Local issue files are authoritative for scope and acceptance evidence.
`GOALS.md` is authoritative for dependencies and project status. GitHub is the
visible mirrored queue. Apply changes locally first, then synchronize GitHub.

If GitHub is required but unavailable, record a blocker and do not authorize
implementation unless the user explicitly waives the mirror requirement.

## Open the implementation gate

After the user explicitly approves the complete local and GitHub issue graph:

- record the approval wording and date;
- set `Issue graph approval` to `Approved`;
- set `Implementation authorized` to `Yes`;
- calculate the initial ready frontier;
- return control to the coordinator so it can invoke `$implement`.

Do not assign workers, change code, create implementation branches, or run
implementation checks in this skill.
