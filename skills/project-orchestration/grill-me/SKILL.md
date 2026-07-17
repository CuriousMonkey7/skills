---
name: grill-me
description: >-
  Build shared understanding of a substantial project through a gated,
  user-led interview before planning or implementation. Use when an idea,
  project, or major change still needs its outcome, users, constraints,
  non-goals, decisions, risks, and acceptance evidence clarified. Do not use
  this skill to create GOALS.md, decompose issues, delegate workers, or
  implement work.
---

# Grill Me

Coordinate the discovery conversation. Resolve only uncertainty that would
materially change the project contract or execution roadmap.

## Preserve the hard gate

1. Inspect only enough supplied and local context to ask informed questions.
2. Ask one to three high-value questions, then stop and wait for the user.
3. Reflect the emerging understanding after each answer before asking the next
   small set of questions.
4. Treat silence, automatic continuation, and generic autonomy instructions as
   no new information.
5. Do not create project artifacts, select technologies, decompose work,
   activate goals, or delegate workers during discovery.
6. Perform research or build a prototype only when the user explicitly
   authorizes it for a named discovery question. Do that work in the
   coordinator thread; do not delegate it.

## Reach shared understanding

Continue until these are sufficiently clear for a durable project contract:

- intended outcome and target users;
- important scenarios and observable behavior;
- constraints and non-goals;
- material product, technical, and operational decisions;
- major risks, unknowns, and dependencies;
- credible project-level completion evidence.

Do not demand a complete specification up front. Let rough ideas develop over
multiple turns and challenge assumptions only when the answer changes scope,
architecture, sequencing, risk, or acceptance.

## Close discovery explicitly

When the project is understood, present a concise `Shared understanding`
summary containing:

- outcome and users;
- in-scope behavior and non-goals;
- accepted decisions and constraints;
- risks and unresolved items;
- proposed completion evidence.

Ask the user to correct or explicitly accept the material assumptions. Do not
infer acceptance from enthusiasm, silence, or a request to continue.

After explicit acceptance, return the summary to the coordinator as the input
for `$to-goals`. Do not create `GOALS.md` yourself.
