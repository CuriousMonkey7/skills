---
name: audit
description: >-
  Independently verify committed project work against its authoritative local
  issue, GOALS.md contract, repository standards, tests, and recorded evidence.
  Use after an implementation commit, after remediation, at milestone
  integration, or before project completion. Return a strict pass/fail result
  and actionable findings; do not implement fixes or silently waive evidence.
---

# Audit

Act as an independent evidence gate. The reviewer running this skill must not
have implemented the work being audited.

## Pin the audit scope

Require:

- audit mode: `Issue`, `Milestone`, or `Project`;
- a fixed point and the exact commit or diff range under review;
- the authoritative local issue for issue mode;
- `GOALS.md` and relevant project instructions;
- the evidence requirements and implementation evidence;
- repository standards and test commands when available.

Resolve the fixed point and confirm the diff is non-empty before reviewing an
issue. If the specification or evidence source is missing, fail with an
evidence gap instead of inventing requirements.

## Review independent axes

Inspect each axis separately so strength in one cannot hide failure in another.

### Contract

- Does the result deliver the issue or milestone outcome?
- Are acceptance criteria satisfied with observable evidence?
- Is required behavior missing, changed, or contradicted?
- Is there unauthorized scope expansion?

### Engineering quality

- Does the change follow repository instructions and established patterns?
- Are public interfaces coherent and implementation complexity contained?
- Are regressions, error paths, security, migration, and compatibility risks
  handled in proportion to the issue?
- Are there actionable defects in the changed lines?

### Feedback integrity

- Did the required tests and checks actually run and pass?
- Does recorded red-green-refactor evidence show a failing check before the
  implementation, or is the approved substitute present with a valid reason?
- Do tests target durable behavior rather than reproduce the implementation?
- Are screenshots, measurements, or manual observations current and relevant?

### Project state

- Do the issue file, `GOALS.md`, GitHub mirror, commits, and repository agree?
- Are dependencies genuinely accepted before dependent work?
- Is the claimed ready frontier or milestone status accurate?

Run safe, relevant checks needed to verify returned evidence. Prefer primary
artifacts and executable observations over summaries.

## Apply mode-specific gates

For an `Issue` audit, verify the full issue commit range, including remediation
commits, against that issue's scope and acceptance evidence.

For a `Milestone` audit, verify the integrated repository, interactions among
all accepted child issues, milestone evidence, and dependency integrity.

For a `Project` audit, also verify every project-level acceptance item and that
all milestones have passing integration audits.

## Return a strict result

Return only:

```text
Result
- PASS or FAIL

Conclusions
- what the implementation does and remaining risks

Findings
- [P0-P3] actionable defect or evidence gap, with file/artifact reference
- None when there are no findings

Evidence inspected
- commits, diffs, tests, commands, artifacts, screenshots, and observations

Required remediation
- changes or missing evidence required for a pass
- None when Result is PASS
```

Use `FAIL` when required evidence is absent, tests fail, the contract is not
met, dependency integrity is broken, or an actionable defect remains. Do not
average axes into a pass.

Do not modify code, create remediation commits, mark objectives complete, or
advance milestones. Return the result to the coordinator, which records it and
dispatches remediation through `$implement` when needed.
