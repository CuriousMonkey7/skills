---
name: evaluate-ml-experiment
description: Evaluate completed, failed, interrupted, or invalid ML experiment attempts against their declared baseline and protocol. Use when Codex must verify result validity, compare metrics and costs, analyze errors, distinguish infrastructure failure from hypothesis failure, update experiment history, decide whether a baseline should be promoted, or recommend the next human-approved research directions.
---

# Evaluate ML Experiment

Evaluate evidence without rewriting history or silently starting new work.

## Verify validity

Confirm that the run used the frozen code/data/config state and declared evaluation protocol. Check artifacts, logs, checkpoint status, sample counts, metric implementation, and important guardrails.

Mark the attempt `invalid` when the result cannot support a scientific conclusion. Treat infrastructure failure or interruption separately from evidence against the hypothesis.

## Compare with the parent

Compare only like-for-like results. Report:

- primary and guardrail metric deltas;
- runtime, compute, and cost;
- uncertainty, variance, and obvious confounders;
- qualitative or slice-level errors that affect the decision;
- whether the hypothesis is supported, rejected, or unresolved.

Record the terminal result, conclusion, artifacts, cost, and W&B reference in the authoritative local ledger. Preserve negative and failed attempts.

## Recommend the next decision

Recommend one of:

- promote the result as the new baseline;
- retain the current baseline;
- repeat within the existing retry contract;
- propose a small next experiment batch;
- stop because the model is good enough or the budget is exhausted.

Explain the evidence and tradeoff briefly. Updating the baseline or executing a scientifically different direction requires explicit user approval. Return recommendations to `$orchestrate-ml-projects` and stop at that gate.
