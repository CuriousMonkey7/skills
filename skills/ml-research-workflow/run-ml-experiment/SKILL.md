---
name: run-ml-experiment
description: Implement, validate, execute, monitor, and resume an explicitly approved ML experiment. Use when an experiment contract already exists and Codex must modify code safely, run preflight checks, fit one batch, perform an end-to-end smoke test, launch a longer CPU/GPU run, track locally and in W&B, checkpoint, recover infrastructure failures, or resume an interrupted batch.
---

# Run ML Experiment

Execute only the approved contract. Use `uv` for Python setup and commands.

## Resume first

Before editing or launching, rebuild state with the sibling `orchestrate-ml-projects/scripts/ml_ledger.py` utility and inspect its next action.

- Reattach when the recorded process or scheduler job is still alive.
- Resume the same attempt only from a valid checkpoint whose code, data, config, and environment identities match.
- Otherwise mark the attempt interrupted and create a linked retry only when budget and retry policy allow it.
- Never repeat a completed experiment automatically.

## Implement safely

Inspect the repository and existing launcher first. Follow normal software practices: keep changes scoped, preserve user work, add proportionate tests, make configuration explicit, and record the exact code/data/config/environment identities.

## Gate expensive execution

Run these stages in order and record each transition locally:

1. Preflight data paths, shapes, splits, labels, metrics, device, storage, W&B mode, checkpoints, and budget.
2. For trainable pipelines, fit one batch and check that forward/backward/optimizer steps, gradients, loss, and checkpoint restore behave sensibly.
3. Run a bounded end-to-end smoke test through data, training or inference, evaluation, local ledger, checkpoints, artifacts, and W&B when configured.
4. Evaluate the short-run evidence. Repair only inside the approved direction and repeat failed gates.
5. Freeze a Git commit or a scoped patch plus hash. Do not include unrelated changes or secrets.
6. Launch the main run only after applicable gates pass.

## Monitor and preserve

Record the host, command, workdir, process/session/job ID, logs, checkpoint, consumed budget, metrics, and W&B run ID. Keep the local ledger authoritative; use W&B for live configs, metrics, artifacts, and monitoring. Continue locally if W&B is offline or unavailable.

When the approved substrate is the Colab CLI, use the sibling `$run-colab-ml-experiments` skill to preserve bounded-job artifacts before shutdown or periodically mirror long-run checkpoints to the local attempt directory. Keep this skill responsible for scientific gates and attempt state.

Stop and request approval if recovery changes the hypothesis, evaluation protocol, planned budget, or scientific direction. Otherwise continue autonomously through monitoring and routine recovery, then hand the terminal attempt to `$evaluate-ml-experiment`.
