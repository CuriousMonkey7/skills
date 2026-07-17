---
name: orchestrate-ml-projects
description: Coordinate human-gated ML model development and improvement from project discovery through approved experiment batches, short-run validation, monitored execution, durable local history, evaluation, and next-direction approval. Use for greenfield ML ideas, existing pipelines or baselines that need evaluation and improvement, interrupted experiment batches that must resume, or multi-step ML research work requiring budgets, GPUs, checkpoints, and W&B tracking.
---

# Orchestrate ML Projects

Own the ML research state machine. Keep scientific direction under human control while continuing routine work autonomously inside an approved experiment contract.

## Resume before planning

1. Search the project root for `ml-workflow/project.md` and `ml-workflow/ledger.jsonl`.
2. If they exist, read [the state model](references/state-model.md) and reconstruct current state with:

   ```bash
   uv run <this-skill>/scripts/ml_ledger.py --root ml-workflow rebuild
   uv run <this-skill>/scripts/ml_ledger.py --root ml-workflow status
   ```

3. Inspect any active external process, scheduler job, logs, checkpoint, and remaining budget before choosing an action.
4. Prefer the reconstructed next action over proposing new work. Never rely on conversation memory for experiment status.

## Route the workflow

Use the sibling skills in this order, entering at the stage supported by durable state:

1. Use `$grill-ml-project` when no accepted project direction exists.
2. Use `$plan-ml-experiments` when a baseline must be established or an accepted direction needs an approval-ready experiment batch.
3. Wait for explicit batch approval and register the immutable contract locally.
4. Use `$run-ml-experiment` for implementation, preflight, fit-one-batch, smoke, snapshot, main execution, monitoring, interruption recovery, and W&B mirroring.
   When the approved execution substrate is the Colab CLI, additionally use `$run-colab-ml-experiments` for named-session lifecycle and verified local artifact mirroring. It does not replace `$run-ml-experiment` or change the approved contract.
5. Use `$evaluate-ml-experiment` for result validity, baseline comparison, conclusions, and recommendations.
6. Stop for human approval before executing a scientifically different direction. Continue without routine approval when the next action remains inside the accepted contract and budget.

## Preserve the authority boundary

- Treat `ml-workflow/ledger.jsonl` as the authoritative event history.
- Treat batch `state.json` files as rebuildable projections, W&B as an operational mirror, and chat history as non-authoritative.
- Distinguish a logical experiment from its execution attempts. Preserve failed, interrupted, cancelled, invalid, and completed attempts.
- Resume the same attempt only when code, data, configuration, and environment identities match a valid checkpoint. Otherwise record interruption and create a linked retry only when the contract permits it.
- Never confuse W&B logging resume with model/optimizer checkpoint resume.
- Do not choose a new hypothesis, evaluation protocol, budget, or deployment scope without user approval.

## Initialize local state

Copy the templates from `assets/` into the project only when no existing ML workflow state is present. Use the ledger utility for all machine-state changes; do not hand-edit `ledger.jsonl`.

Keep exactly one active batch unless the approved project contract explicitly permits independent concurrent batches.
