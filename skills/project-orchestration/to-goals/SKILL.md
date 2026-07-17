---
name: to-goals
description: >-
  Turn explicitly accepted project discovery into an approval-ready GOALS.md
  that combines the stable project contract with the mutable execution control
  plane. Use after shared understanding is complete and before creating
  execution issues. Synthesize what is already known; do not restart discovery,
  delegate workers, or implement work.
---

# To Goals

Convert accepted discovery into the single authoritative project map.

## Require an accepted input

Proceed only when the user has explicitly accepted a shared-understanding
summary covering outcome, users, scope, constraints, decisions, risks, and
completion evidence. If a material item is absent, return to `$grill-me` for
that question instead of inventing an answer.

## Synthesize, do not interview again

1. Read the accepted conversation, relevant project instructions, and existing
   destination documents.
2. If `GOALS.md` already exists, update it from its recorded state rather than
   creating a competing roadmap.
3. Otherwise copy [the GOALS template](assets/GOALS.template.md) to the project
   root as `GOALS.md` and replace every placeholder.
4. Use the project's established vocabulary. Record uncertainty explicitly;
   do not turn guesses into decisions.
5. Keep stable agreement under `Project contract` and changing coordination
   state under `Execution control`.

## Define acceptance before execution

For the project and every milestone, record observable evidence that can prove
the outcome. Prefer executable tests, inspectable artifacts, user-visible
behavior, measurements, and independent review over activity statements.

Set the planning gate to:

```text
GOALS approval: Pending
Issue graph approval: Pending
Implementation authorized: No
```

Do not create issue files, publish GitHub issues, activate implementation,
create a dashboard, or delegate workers.

## Obtain explicit approval

Present the completed `GOALS.md` and call out material assumptions. Ask the user
to correct or explicitly approve it. When approved:

- record the approval date and the user's approval wording;
- set `GOALS approval` to `Approved`;
- leave `Implementation authorized` as `No`;
- return control to the coordinator so it can invoke `$to-issues`.

Do not interpret approval of `GOALS.md` as approval of an issue graph that does
not yet exist.
