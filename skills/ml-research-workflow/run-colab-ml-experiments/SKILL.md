---
name: run-colab-ml-experiments
description: Run an explicitly approved ML experiment on Google Colab through the Colab CLI while preserving checkpoints and artifacts locally without mounting Google Drive. Use alongside orchestrate-ml-projects and run-ml-experiment when Colab is the selected execution substrate, for bounded jobs that must download artifacts before shutdown, or long jobs that require periodic checkpoint mirroring to the Mac.
---

# Run Colab ML Experiments

Use Colab only as an execution substrate. Keep `ml-workflow/ledger.jsonl` authoritative and preserve the human approval, identity, retry, and budget boundaries owned by `orchestrate-ml-projects` and `run-ml-experiment`.

## Enter safely

1. Rebuild the ML ledger and confirm that the attempt is approved and ready for its recorded phase.
2. Inspect `colab sessions`, any recorded Colab session, the remaining wall-time/cost budget, local disk space, and existing local checkpoints before allocating compute.
3. Install the CLI with `uv tool install google-colab-cli` only when missing. Complete any first-use OAuth consent with the user; do not automate account login or consent.
4. Name the Colab session from the attempt ID. Record `substrate=colab`, session ID, `/content` workdir, exact command, log location, observation time, and budget through the ML ledger utility.
5. Map each required remote artifact to a destination under `ml-workflow/runs/<attempt-id>/`. Include model and optimizer state for a resumable training checkpoint. Never put credentials in commands, manifests, logs, or the ledger.

Do not use `colab drivemount`. Use direct CLI downloads for bounded jobs and the bundled sync script for long jobs.

## Preserve a bounded job

Run the approved command, then download and verify every required artifact before stopping the VM:

```bash
colab new -s <session> --gpu <approved-gpu>
colab exec -s <session> -f <approved-script.py>
uv run <this-skill>/scripts/sync_colab_artifacts.py once \
  --session <session> \
  --artifact /content/checkpoints/latest.pt=ml-workflow/runs/<attempt-id>/checkpoints/latest.pt \
  --artifact /content/results.json=ml-workflow/runs/<attempt-id>/results.json \
  --manifest ml-workflow/runs/<attempt-id>/colab-sync.jsonl
colab log -s <session> -o ml-workflow/runs/<attempt-id>/colab-log.ipynb
```

After the sync exits zero, validate the checkpoint against the attempt's code, data, config, and environment identities; record it with `ml_ledger.py checkpoint`; then stop the session. If any required download or verification fails, leave the session alive, inspect it, and retry while budget permits. Never stop while the only valid copy of a required artifact remains on the VM when in-contract recovery remains possible.

## Mirror a long job

Require the training code to write checkpoints atomically on the VM and create a completion sentinel only after final files are flushed. Start the approved execution and the watcher as separate local processes:

```bash
uv run <this-skill>/scripts/sync_colab_artifacts.py watch \
  --session <session> \
  --artifact /content/checkpoints/latest.pt=ml-workflow/runs/<attempt-id>/checkpoints/latest.pt \
  --artifact /content/checkpoints/trainer-state.json=ml-workflow/runs/<attempt-id>/checkpoints/trainer-state.json \
  --completion-remote /content/attempt.complete \
  --interval-seconds 120 \
  --max-seconds <remaining-approved-wall-seconds> \
  --manifest ml-workflow/runs/<attempt-id>/colab-sync.jsonl
```

The watcher downloads to temporary files, hashes them, and atomically replaces local copies. It never stops the Colab session. Exit zero means the sentinel was observed and a final complete sync succeeded. Any other exit requires inspection; do not infer experiment completion from a locally mirrored checkpoint.

Record periodic execution and budget observations in the ledger. After the execution and watcher finish, validate and record the final checkpoint, export the Colab log, record terminal evidence, and stop the session.

## Recover safely

- Reinspect `colab sessions`, `colab status -s <session>`, remote files, local manifests, logs, and remaining budget before acting on a stale handle.
- Restart the watcher against the same destinations after a local interruption; atomic replacement protects the last verified local copy.
- Treat `colab-sync.jsonl` as transfer evidence, not authoritative workflow state.
- Resume the same attempt only when a locally verified checkpoint contains the required state and matches all four recorded identities.
- If the remote session was pruned, preserve the last verified local copy and follow the ledger's interruption/retry policy.
- If recovery cannot finish within the approved budget or runtime lifetime, make one final bounded recovery attempt, record the interruption and missing artifacts, stop the billable session, and report the loss. Never silently exceed the contract to keep a VM alive.
- Archive a remote directory into one file before downloading it; the sync script operates on files.
- Do not confuse W&B resumption or a completion sentinel with a valid model checkpoint.
