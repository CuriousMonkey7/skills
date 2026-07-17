---
name: grill-ml-project
description: Interview the user to shape an ML project before experiments begin. Use for greenfield model ideas, vague ML requirements, existing pipelines that need improvement, or any ML task where objectives, data, metrics, baseline, compute, budget, checkpointing, W&B, deployment scope, or stopping conditions are not yet agreed.
---

# Grill ML Project

Build shared understanding without implementing the model.

## Discover the starting point

First determine whether this is:

- greenfield work with no reliable baseline; or
- an existing pipeline, model, or result that should be evaluated and improved.

Inspect provided code, data documentation, results, and configs before asking questions they already answer.

## Interview efficiently

Ask one to three high-value questions per turn. Follow the uncertainty; do not force every project through a fixed questionnaire.

Resolve what matters for this project:

- model outcome and real user value;
- available data, labels, splits, leakage risks, and constraints;
- current baseline and known failure modes;
- primary metric, guardrail metrics, and evaluation protocol;
- acceptable budget, runtime, GPU/compute environment, and stopping conditions;
- checkpoint/resume capability, artifact retention, and W&B availability;
- deployment or production scope, only when relevant;
- promising initial directions and decisions that remain human-controlled.

Do not choose an architecture merely to end discovery. Surface tradeoffs and recommend a default when evidence supports one.

## Close the gate

End with a concise `Shared understanding` covering outcome, starting point, evaluation, constraints, compute, budget, scope, risks, and completion evidence.

Wait for explicit user acceptance. Do not implement, launch jobs, or approve experiments in this skill. Return accepted state to `$orchestrate-ml-projects` for durable recording and planning.
