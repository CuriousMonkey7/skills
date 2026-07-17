---
name: plan-ml-experiments
description: Turn an accepted ML project direction, baseline, or evaluation finding into a bounded experiment or dependency-linked experiment batch. Use when Codex must establish a baseline, formulate hypotheses, freeze an evaluation protocol, allocate compute and retry budgets, define stopping rules, or prepare experiments for explicit user approval.
---

# Plan ML Experiments

Plan the smallest batch that can answer the current scientific question.

## Establish the reference

- For greenfield work, make pipeline correctness and a simple baseline the first objective.
- For existing work, identify the exact baseline run, code/data/config state, and evaluation protocol.
- Do not compare experiments that use incompatible evaluation protocols.

## Design the batch

Give each logical experiment one hypothesis and one interpretable change. Use dependencies only when later experiments genuinely require earlier evidence.

Define:

- hypothesis and expected mechanism;
- parent/baseline;
- trainable or evaluation-only kind;
- configuration and intended code surface;
- evaluation protocol and decision mapping;
- planned compute, `max_runs`, cost/time budget, and stopping conditions;
- retry limit, checkpoint policy, and artifact retention;
- fit-one-batch and smoke requirements;
- outcome that would support, reject, or leave the hypothesis unresolved.

Use the contract schema and template from the sibling `orchestrate-ml-projects` skill. Keep the batch narrow; defer unrelated ideas.

## Obtain approval

Show the ordered or dependency-linked batch, total budget, and what will happen for each result. Wait for explicit approval.

After approval, freeze and register the contract with the local ledger. Do not implement or execute experiments in this skill. Any new hypothesis, protocol, or budget requires another approval.
