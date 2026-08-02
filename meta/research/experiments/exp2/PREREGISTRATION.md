# Pre-registration: Experiment 2 — ACE-100 where documentation is load-bearing

**Status:** Registered. Written while Experiment 1's data collection was still in
progress and **before any cross-arm analysis existed**: at commit time, 41 of 72
Experiment 1 cells were complete and neither `evaluate` (tests, judge) nor `analyze`
had run on any of them. Amendments follow Experiment 1's rules.

**Relationship to Experiment 1**
(`../exp1/PREREGISTRATION.md`): same repository, same pinned commit, same three
documentation treatments — the arms are **reused artifacts**, byte-identical to
Experiment 1's (hashes in `../exp1/audit/arm-gates/`). Experiment 1 asks what
ACE-100 does on mechanically-sampled realistic tasks; Experiment 2 asks what it
does **where documentation verifiably matters**, and adds mechanism
instruments. Each experiment reports in its own paper; confirmatory families
are never pooled.

## 1. Research questions

- **RQ1 (concentration):** Do ACE-100's cost/quality effects appear on tasks that
  verifiably require documentation?
- **RQ2 (findability):** Can agents locate documented facts more cheaply/accurately
  under ACE-100's architecture than under the original or naive forms?
- **RQ3 (docs-value):** What fraction of documentation's task value does each form
  deliver, relative to a no-docs floor?

## 2. Conditions (four)

| Condition | Docs corpus in workspace |
|---|---|
| **no-docs** | Corpus-manifest paths deleted; nothing overlaid (the floor) |
| **original** | Experiment 1's original arm |
| **ace** | Experiment 1's ace arm |
| **naive** | Experiment 1's naive arm |

## 3. Task selection

Base filters as Experiment 1 §4 as amended (18-month window from the selection run,
≥2 changed files, CI passed, bot authors excluded, not primarily documentation,
linked issue or ≥200-char body), with two registered differences:

1. **Changed-lines band 30–800** (complex features exceed Experiment 1's 400).
2. **Doc-reference requirement:** the PR body or linked-issue body matches
   `docs/[\w/.-]+\.md`, `CONTRIBUTING.md`, `AGENTS.md`, or `coding-guidelines`
   (case-insensitive) — a human demonstrably invoked the documentation.

**Seed 20260802.** Sample **8 candidates** (stratified best-effort across the
Experiment 1 strata). Issue comment threads are never included in prompts; PR/issue
*bodies* that cite doc paths flow into prompts by design — that contact-rate
amplification is arm-constant and is the selection intent.

**Ablation screening (doubles as data):** each candidate runs one pilot in
**original** and one in **no-docs**. A candidate is *retained* if no-docs degrades:
a suite or reference-test failure absent from the original pilot, or — both passing —
blinded-judge quality lower by ≥1 point on any dimension. Retain 4–6 tasks (if more
qualify, first 6 in seeded order; if fewer than 4, redraw 4 further candidates and
repeat once, logged). Screening references only original/no-docs — treatment-blind.
Pilots are retained as trial 1 of their condition.

## 4. Runs

Target 6 tasks × 4 conditions × **4 trials** = 96 cells (pilots folded in).
Protocol identical to Experiment 1 §5: Claude Sonnet 5 pinned, harness defaults
(documented in `../exp1/audit/harness-environment.json`), 200 turns / 45 min /
$15 caps, network off, fresh workspace per run, cells randomized and interleaved
(order seed 20260802), failures recorded not rerun, infra failures retried.
Collection begins only after Experiment 1's schedule has fully completed.

## 5. Instruments

1. **Experiment 1 endpoints:** per-run cost at standard prices; suite and
   reference-test outcomes; blinded judge (same rubric, double-scored subset).
2. **Documented-convention conformance checklist** (new): per task, before any
   non-pilot cell runs, a checklist is derived from the reference PR and the
   original docs; each item states the requirement, its documentation source, and
   its channel (docs-only / ambient CLAUDE.md-closure / code-visible). Every diff is
   scored objectively against it. Checklists are committed before use.
3. **Retrieval-QA findability probe** (new): ~50 factual questions generated from
   the original corpus (paraphrased; answers verified present in all three docs
   arms — the preservation gate guarantees fact survival). Each question is put to a
   budgeted agent (small turn cap) once per **all four** conditions. The no-docs
   baseline directly measures training-data contamination per question (questions
   answerable without docs are contaminated and analyzed separately). Scored:
   semantic accuracy (judge), tokens, turns.
4. **Mechanism metrics** from transcripts: doc tokens ingested (explicit reads plus
   the per-arm ambient constants), consultation events, turns-to-first-edit.

## 6. Hypotheses (confirmatory for this experiment)

- **H3 (cost):** on retained tasks, ace is ≥20% cheaper than original
  (task-median per-run cost ratio ≤ 0.80).
- **H4 (quality non-inferiority):** as Experiment 1 H2 (5 pp test-pass /
  0.5 rubric points), plus conformance-checklist rate within 10 pp.
- **H5 (findability):** on non-contaminated QA questions, ace achieves
  tokens-per-correct-answer ≥20% lower than original, with accuracy non-inferior
  (within 5 pp).
- **RQ3 readout (descriptive):** value retention = (condition − no-docs) /
  (original − no-docs) per endpoint.
- **Exploratory:** task-class × arm interaction across the two experiments.

## 7. Analysis

As Experiment 1 §7: within-task pairing, per-task medians, bootstrap CIs,
estimation over p-values. Pairwise condition comparisons; no pooling with
Experiment 1's families.

## 8. Honesty apparatus

The arms **predate** this selection (built 2026-08-01, before this document), so
Experiment 1's temporal firewall does not apply here. Mitigations: selection is
fully mechanical with zero per-task discretion; treatment construction never saw any
task list (still true — the migration sessions predate both experiments' manifests);
ablation screening is treatment-blind; and this registration commits while
Experiment 1's collection is demonstrably unanalyzed (snapshot above). Residual
risk — that mechanically-selected doc-referencing tasks happen to favor content ACE
preserved well — is bounded by the preservation gate (facts verified present in all
arms) and disclosed.

## 9. Threats to validity (beyond Experiment 1's)

Wider line band admits harder tasks (cap-hit rates reported); doc-citing prompts
raise doc-contact rates in all conditions (scope: results generalize to tasks whose
discussion invokes documentation); QA questions generated from original text may
retain lexical bias toward the original arm despite paraphrasing (reported);
training-data contamination measured directly via the no-docs QA baseline.

## 10. Budget and layout

~96 subject cells plus 16 pilot-covered runs (~$150–280 at standard-price
accounting, subscription-billed); QA probe ~200 short runs (~$20–40 API); judging
and checklist scoring (~$40–60 API). Additional API credits to be added before the
evaluation phase. Layout mirrors Experiment 1 under
`meta/research/experiments/exp2/` (data gitignored, published as release
assets); arms referenced from `../exp1/arms`, hash-pinned via Experiment 1's
audit. This experiment reports in `meta/research/papers/exp2/`, created when
there are results to report.

## Amendments

### Amendment 1 — path corrections; one paper per experiment (2026-08-02)

Made before any data collection for this experiment, so the body text is
corrected in place rather than only annotated; this amendment records what
changed. **No hypothesis, condition, instrument, or threshold changes.**

**Paths.** References in §Relationship, §4, and §10 pointed at
`meta/experiment/`, `../experiment/`, and `meta/experiment2/`, paths that
stopped existing when the
research tree was split into shared tooling and per-experiment directories
(Experiment 1's Amendment 6). They now read `../exp1/` and
`meta/research/experiments/exp2/`.

**Reporting.** §Relationship stated that one paper reports both experiments.
Each experiment now reports in its own paper (Experiment 1's Amendment 7).
Experiment 1's paper is complete and tagged `paper-exp1-v1`; it cites this
registration as future work and does not depend on this experiment's outcome.

This experiment's paper cites `paper-exp1-v1` for Experiment 1's arguments and
`../exp1/analysis/summary.json` for any Experiment 1 number it restates, so a
correction to that data propagates. Reusing Experiment 1's arms as
hash-pinned artifacts is unaffected: shared artifacts are not shared reporting,
and confirmatory families remain unpooled.
