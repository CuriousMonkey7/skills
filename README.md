# Skills

Composable agent skills for software-project delivery and human-gated ML
research workflows.

The project keeps planning human-controlled and makes implementation autonomous
only after two explicit approvals:

```text
grill-me
  → to-goals
  → explicit GOALS.md approval
  → to-issues
  → explicit issue-graph approval
  → implement
  → audit
```

The ML workflow keeps scientific direction human-controlled while allowing
approved, budget-bounded experiments to run autonomously:

```text
grill-ml-project
  → plan-ml-experiments
  → explicit experiment-batch approval
  → run-ml-experiment
  → fit-one-batch and smoke gates
  → main run
  → evaluate-ml-experiment
  → next-direction approval
```

## Project orchestration skills

| Skill | Responsibility |
| --- | --- |
| `orchestrate-projects` | Route the complete workflow and maintain authoritative project state |
| `grill-me` | Develop shared understanding without starting implementation |
| `to-goals` | Convert accepted discovery into an approval-ready `GOALS.md` |
| `to-issues` | Create dependency-linked local issues and GitHub mirrors |
| `implement` | Schedule and execute approved issues through tested commits |
| `audit` | Independently verify issues, milestones, and final project evidence |

`GOALS.md` is the project control plane. Local issue files own issue scope and
acceptance criteria. GitHub issues mirror the visible execution queue.

## ML research workflow skills

| Skill | Responsibility |
| --- | --- |
| `orchestrate-ml-projects` | Route the research loop and resume durable project state |
| `grill-ml-project` | Agree on the objective, data, metrics, compute, budget, and stopping conditions |
| `plan-ml-experiments` | Turn an accepted direction into an approval-ready experiment batch |
| `run-ml-experiment` | Implement, validate, run, monitor, checkpoint, and resume approved experiments |
| `evaluate-ml-experiment` | Validate results, compare baselines, preserve conclusions, and recommend next directions |

The project-local ledger is authoritative for experiment history and resume
state. Weights & Biases is an optional operational mirror.

## Install

Install with the Agent Skills installer:

```bash
npx skills@latest add CuriousMonkey7/skills
```

Select the skills you want and the supported coding agents where they should be
installed. The repository uses the open Agent Skills directory format and can
be used by Codex and other compatible agents.

## Start a project

Invoke the coordinator:

```text
Use $orchestrate-projects to shape this project with me, then deliver it
autonomously after I approve the plan and issue graph.
```

The coordinator will not delegate workers, create implementation commits, or
activate implementation objectives during discovery or issue planning. Once
both gates are approved, it schedules the ready issue frontier sequentially or
in parallel according to dependencies and change overlap.

## Start an ML project

Invoke the ML coordinator for either a greenfield idea or an existing model:

```text
Use $orchestrate-ml-projects to understand this ML project, agree on a bounded
experiment batch with me, and execute it after I approve the batch.
```

The coordinator resumes from the local ledger before planning new work. It
requires fit-one-batch and end-to-end smoke validation before a longer training
run when those gates apply, and stops for approval before changing scientific
direction or budget.

## Repository layout

```text
skills/
├── project-orchestration/
│   ├── orchestrate-projects/
│   ├── grill-me/
│   ├── to-goals/
│   ├── to-issues/
│   ├── implement/
│   └── audit/
└── ml-research-workflow/
    ├── orchestrate-ml-projects/
    ├── grill-ml-project/
    ├── plan-ml-experiments/
    ├── run-ml-experiment/
    ├── evaluate-ml-experiment/
    └── tests/
```

Future skill families can be added as sibling directories under `skills/`.

## Design principles

- One authoritative `GOALS.md` project map.
- Explicit human approval before autonomous implementation.
- Vertical-slice issues with an acyclic dependency graph.
- Parallel execution only for unblocked, non-overlapping work.
- TDD where practical, otherwise a named executable feedback loop.
- Stable implementation commits before independent review.
- Failed audits return to remediation and never advance project state.
- Final completion requires project-level evidence and an independent audit.

## License

[MIT](LICENSE)
