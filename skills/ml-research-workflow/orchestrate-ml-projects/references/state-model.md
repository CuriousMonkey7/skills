# ML workflow state model

Read this reference when initializing, resuming, repairing, or inspecting an ML experiment batch.

## Durable layout

```text
ml-workflow/
├── project.md
├── ledger.jsonl
├── batches/<batch-id>/
│   ├── contract.json
│   └── state.json
└── runs/<attempt-id>/
    └── state.json
```

- `project.md` records the accepted project direction, current baseline, current batch, budget, and human decisions.
- `contract.json` is the immutable approved batch contract.
- `ledger.jsonl` is the append-only authority for operational state.
- `state.json` files are atomic, rebuildable projections for fast inspection.
- Run directories may additionally contain scoped patches, logs or log references, checkpoints or checkpoint references, results, and artifacts.

## Identity hierarchy

1. A batch is an immutable user-approved collection of logical experiments.
2. A logical experiment owns a hypothesis, configuration, parent/baseline, evaluation protocol, dependencies, and retry limit.
3. An attempt is one execution history for a logical experiment.
4. A resumed process remains the same attempt only when its valid checkpoint matches the attempt's code, data, configuration, and environment identities.
5. A clean restart without a matching checkpoint is a new attempt linked to the same logical experiment.

## Attempt phases

```text
planned → implementing → preflight → fit-one-batch → smoke
        → snapshot → main-run → evaluating → terminal
```

Evaluation-only workflows may move from `preflight` directly to `smoke`. Terminal statuses are `completed`, `failed`, `interrupted`, `cancelled`, and `invalid`.

Repeat a failed short gate only after recording the failure and making an in-contract repair. Do not launch a main run until all applicable gates pass and an immutable code/configuration snapshot is recorded.

## Resume decision

Apply the first matching rule:

1. If the recorded process or scheduler job is still alive, reconnect and monitor it.
2. If the process stopped and a valid checkpoint matches all identities, resume the same attempt and reuse the W&B run ID for logging when possible.
3. If no matching checkpoint exists, mark the attempt interrupted.
4. If retry count and remaining budget permit, start a new linked attempt from the last safe idempotent phase.
5. If retry or budget is exhausted, stop and report the blocker.
6. After a terminal completed experiment, select only the next dependency-unblocked logical experiment. Never repeat completed work automatically.

Always inspect external execution state before acting on a stale handle. W&B run resumption does not establish that model state is resumable.

## Required batch contract fields

- `schema_version`
- `batch_id`
- `approval.status` and `approval.approved_at`
- `baseline_id`
- `evaluation_protocol`
- `budget`
- `stopping_conditions`
- `decision_mapping`
- `experiments[]` with unique `experiment_id`, `hypothesis`, `kind`, `parent_id`, `config`, `depends_on`, and `retry.max_attempts`

Each `parent_id` must identify the batch baseline or another logical experiment. When the parent is another experiment, include it in `depends_on`. Dependencies must refer to experiments in the same batch and form an acyclic graph.

Default `allow_concurrent_batches` to false. Reject another batch while an existing batch remains actionable unless the newly approved contract explicitly sets it to true.

When a terminal failed or otherwise blocked batch has no running attempts and a human has reviewed its outcome, close it with a durable `batch_closed` event and reason before registering the next sequential batch. Never close a batch merely to bypass retry or budget policy.

## Ledger rules

- Append one complete JSON object per line.
- Persist an event before exposing its projected state.
- Rebuild projections after any disagreement or interrupted write.
- Never remove or rewrite historical events.
- Avoid secrets in environment snapshots, commands, patches, and W&B metadata.

## Required attempt schemas

Record identities as an object with non-empty `code`, `data`, `config`, and `environment` values. Reject checkpoint resumption when any value differs.

Record an execution handle with:

- `substrate`, `host`, and `working_directory`
- exact `command`
- at least one of `process_id`, `session_id`, or `job_id`
- `status` and `observed_at`
- `log_location`
- nullable `wandb_run_id`
- absolute `consumed_budget.cost` and `consumed_budget.wall_seconds`

Record a checkpoint with `path`, boolean `valid`, `contains`, matching `identities`, and `recorded_at`. A trainable attempt is resumable only when a valid checkpoint contains both model and optimizer state.

Record a terminal result with boolean `valid`, `metrics`, absolute `cost`, `artifacts`, W&B mode/run metadata, and a non-empty `conclusion`.

## Budget projection

Accept one or more limits: `max_runs`, `max_cost`, and `max_wall_seconds`. Count attempts as runs and aggregate absolute cost and wall-time observations across attempts. Project limits, consumed amounts, remaining amounts, and exhausted dimensions into batch `state.json`. Use `max_runs` to admit new attempts; do not stop an admitted attempt merely because it consumes the final run slot. Block budget-consuming transitions after cost or wall time is exhausted, reject decreasing observations, and preserve evaluation and terminal recording.

## Event types

- `project_initialized` and `project_updated`
- `batch_registered` with the full immutable contract and its SHA-256
- `batch_closed` with a non-empty reviewed reason
- `attempt_started` with identities and nullable retry parent
- `phase_changed`
- `execution_observed`
- `checkpoint_recorded`
- `budget_recorded`
- `attempt_finished`

Each event includes schema version, event ID, UTC timestamp, and the relevant batch, experiment, and attempt IDs. Treat a malformed newline-terminated event as corruption. Recover an interrupted non-newline final append by truncating only the invalid tail and replaying the valid prefix.

Render `project.md` only from durable event timestamps and state. Include the active batch, its projected budget, stored human decision state, and next action so identical ledgers rebuild to identical bytes.
