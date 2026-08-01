# Pre-registration: An empirical evaluation of ACE-100 against its stated goals

**Status:** Registered. This document was written and committed before repository
selection, task selection, migration, or any experimental run. Any later change is
recorded in the Amendments section with a rationale and its own commit; no amendment
may follow the data collection it affects.

**Artifact under test:** ACE-100 kit, Issue 3 (this repository, release tag `issue-3`).

**Output:** a self-published preprint (~8–12 pages, written to workshop-submittable
standard) plus this repository's `meta/experiment/` tree and a published raw-data
archive.

---

## 1. Claim under test

ACE-100's stated purpose (docs/standard/about.md): "LLM agents read documentation into
a limited context window. Excess text decreases the quality of their work and increases
cost." The testable claim is that adopting the kit **as a bundle** (controlled grammar +
compression + document architecture) improves agent cost without degrading work quality.

**H1 — Cost superiority.** Agent runs on the ACE-100 arm cost ≥20% less than runs on
the original-docs arm, on the task-median of per-run cost.

**H2 — Quality non-inferiority.** ACE-100-arm quality is not worse than original-arm
quality by more than the margin: 5 percentage points on task-median test-pass rate,
and 0.5 points on the 1–5 judge rubric.

Cost is computed from per-run token usage at **standard published prices** (not
time-limited introductory prices), so reported numbers are stable over time.
Component isolation (grammar vs. architecture within ACE-100) is out of scope; the
control arm isolates the bundle from mere compression. Future work.

## 2. Design: three arms

One open-source repository, three documentation states, identical code:

| Arm | Construction |
|---|---|
| **original** | Repo at pinned commit, docs untouched. |
| **ace** | Docs migrated by the kit's own advertised path (`adopt.sh --migrate`, `ace-migrate` skill), performed once by Claude Opus 5. |
| **naive** | Original docs compressed in place by Claude Opus 5, one pass, prompt: "rewrite to approximately N tokens; preserve all factual and procedural content; no other constraints." Original file paths and boundaries preserved; no indexes, no front matter, no ACE vocabulary. |

Interpretation: naive-vs-original measures the effect of length alone; ace-vs-naive
measures what the spec adds beyond length; ace-vs-original is the headline adopter
comparison.

**Gates (all pass before any experimental run):**

1. `tools/check.sh` passes on the ace arm with zero unexplained violations.
2. `tools/measure.py` snapshots recorded for all three arms. The naive arm's total
   corpus token count must be within ±10% of the ace arm's; otherwise the naive arm
   is rebuilt until matched.
3. Semantic-preservation check on **both** rewritten arms: an LLM-judge pass compares
   each rewritten doc against its original and flags dropped factual or procedural
   content. Flags are repaired before the firewall date is stamped; the repair log is
   published in the paper's appendix.

## 3. Repository selection criteria (fixed before scouting)

Chosen against these criteria, in descending priority; no candidate was favored at
registration time:

1. **Docs are load-bearing** — conventions, architecture decisions, or configuration
   semantics live in prose, not recoverable from source alone.
2. **Monorepo or multi-package** — ACE-100's document architecture is its distinctive
   part and must be exercised.
3. **Ground truth exists** — active merged-PR history usable as tasks with reference
   implementations.
4. **Cheap, real test suite** — quality partially measurable objectively.
5. **Permissive license; ~20–150 doc files** — publishable fork; migration affordable.

A manipulation check (§6) verifies criterion 1 empirically during runs.

## 4. Task selection (mechanical; temporal firewall)

**Filters** over merged PRs: merged within ~18 months of selection; touches ≥2 files;
has a linked issue or self-contained description; reference diff 30–400 changed lines;
CI passed on merge; not primarily a documentation change.

**Procedure:** filter → stratify by task type (feature addition / bug fix or behavior
change / configuration-integration) → seeded random sample within strata.
**Sampling seed: 20260801.** Target 6 tasks (acceptable range 5–8). No human picks
individual tasks. A sampled task may be dropped only for a stated, logged
infrastructure reason (e.g., requires credentials the sandbox lacks), with a seeded
redraw; the drop log is published.

**Temporal firewall:** task selection completes before the ace and naive arms are
built; the migration and compression agents never see the task list; doc rewrites
cannot be tuned to the tasks. Both facts are stated in the paper.

## 5. Execution protocol

- **Subject model:** Claude Sonnet 5 (`claude-sonnet-5`), pinned, default effort and
  thinking settings, for all arms. **Side-measurement:** 2 tasks repeated on Claude
  Opus 5, 2 trials per arm, to observe whether the effect shrinks with model
  capability. Collection window: August 2026, dates recorded.
- **Trials:** 4 per (task × arm) cell. ~72 subject runs + ~12 side-measurement runs.
- **Harness:** headless Claude Code via the Claude Agent SDK, versions pinned. Fresh
  clone of the arm's repo state per run, discarded after. **Network off** (no web
  search/fetch): in-repo docs are the sole documentation channel — acknowledged as a
  limitation.
- **Prompt:** the task's issue/PR description, cleaned of spoilers (links to the PR,
  its diff, or its authors), plus a fixed generic implement-this instruction.
  **Documentation is never mentioned in the prompt.** Identical prompt bytes across
  arms.
- **Caps:** 200 turns, 45 minutes wall-clock, $15 computed cost per run. A run that
  crashes or hits a cap is recorded as failed in its arm — never silently rerun.
  Reruns only for infrastructure faults (harness bug, API outage), logged.
- **Order:** (task × arm × trial) cells randomized and interleaved across the
  collection window.
- **Captured per run:** full transcript; token usage split into input / output /
  cache-read / cache-write; computed cost; turn count; wall-clock; produced diff;
  list of files read (docs-usage manipulation check: whether and how many doc tokens
  each arm's agent pulled into context).

**Replication stance:** no seed exists at the API level; inference is nondeterministic.
Replication is procedural (pinned models, harness, commits, prompts, configs, seeds for
our own randomness), statistical (distributions across trials, not single runs), and
data-level (raw transcripts and per-run records published).

## 6. Quality evaluation (hierarchy fixed in advance)

1. **Primary — test outcomes:** (a) the repo's existing suite (regressions);
   (b) tests added by the reference PR, run against the agent's implementation
   (delivered behavior).
2. **Secondary — blinded LLM judge:** Claude Opus 5 scores each diff against the task
   description and reference implementation on a fixed rubric — correctness,
   completeness, convention adherence, each 1–5. Arm labels stripped; doc-style tells
   scrubbed as far as possible; diffs judged independently in randomized order; run
   via the Batches API. **Reliability:** a subset is double-scored; agreement is
   reported. Judge blinding limits are acknowledged.
3. **Descriptive only:** completion rate, turn count, wall-clock.

## 7. Analysis plan

- Within-task pairing: every task appears in every arm; all comparisons are
  within-task.
- Report per-task medians with spreads, and effect sizes (cost ratios, quality
  deltas) with bootstrap confidence intervals. **Estimation over p-values**; a
  Wilcoxon signed-rank on task medians appears as a supplement only.
- Decision rules: H1 supported if the task-median cost ratio (ace/original) ≤ 0.80.
  H2 supported if quality deltas are within the §1 margins, CI permitting. All three
  pairwise arm comparisons reported regardless of outcome.
- **Migration economics:** full one-time migration cost (tokens and dollars) reported
  as a headline number, with break-even: the number of agent runs at observed per-run
  savings for migration to pay for itself.

## 8. Threats to validity (to be reported)

Single repository; single primary subject model; LLM-judge blinding is imperfect;
network-off is unrealistic for production agents; migration performed by a stronger
model than the subject (documented asymmetry); the evaluators are the spec's authors —
mitigated by this pre-registration, mechanical task selection, the temporal firewall,
and full artifact release. Training-data contamination (added by Amendment 1): the
subject model may know the target repository's documentation from pretraining, which
dilutes the in-repo-docs manipulation; partially observable via the docs-usage
manipulation check, and irreducible for any repository with a real PR history.

## 9. Artifacts and layout

- `meta/experiment/` (this tree): pre-registration, pipeline tools (`select-tasks`,
  `build-arms`, `run-cell` + scheduler, `evaluate`, `analyze`), task manifest,
  analysis outputs, paper source. `meta/` is excluded from kit governance and release
  (`.ace-ignore`, `meta/publish.sh`).
- Arm states: branches on a public fork of the target repo, referenced here by commit
  hash.
- Raw run data (transcripts, diffs, judge outputs): `meta/experiment/data/`,
  gitignored; published as a release asset or data DOI. The repo stores hashes and
  pointers.
- Estimated budget: ~$200–350 subject runs and evaluation; migration and arm
  construction reported separately.

## Amendments

### Amendment 1 — target repository selected (2026-08-01)

**Target repository: `open-telemetry/opentelemetry-collector`.** Chosen against the
§3 criteria from a verified shortlist (40 repositories scouted across six search
angles; the top 8 by independent-mention count were clone-inspected; evidence
archived in `scouting/shortlist.json`). Rationale: the only high-scoring candidate
with no disqualifiers — ~92 curated in-repo markdown docs (within the 20–150 band)
including MUST-level prose conventions not recoverable from source
(`docs/coding-guidelines.md`); genuinely multi-module (100 `go.mod` files); ~1,775
merged PRs in 18 months (~813 substantive) clustering in the 30–400 line band;
credential-free local `go test` suite; Apache-2.0.

This amendment also adds the training-data-contamination threat to §8. No tasks had
been selected and no arms built at the time of this amendment.

### Amendment 2 — task-selection filter corrections; a discarded draw (2026-08-01)

Made after a first selection draw and **before any arm construction or run** (the
temporal firewall had not been stamped). Three changes to the §4 procedure:

1. **Bot-authored PRs are excluded** (author matching `[bot]`/renovate/dependabot/
   github-actions). Rationale: an initial draw sampled two renovate dependency bumps —
   generated PR bodies defeat the description filter, and mechanical version bumps are
   not replayable engineering tasks. This closes a gap between the registered filters
   and their stated intent ("realistic task ... reference implementation").
2. **The first-pass window is recorded** in the manifest (`limit`, considered-PR count
   and number range). Two same-day draws produced different eligible pools (500- vs
   1000-PR windows; GitHub check-data availability also varies), so the considered
   window is now part of the audit trail. The registered window parameter is
   `--limit 1000`.
3. **Cross-repository linked issues no longer abort selection** — a linked issue that
   cannot be fetched from the target repo (e.g. it lives in the contrib repo) is
   recorded with `fetch_failed` and the PR body alone carries the prompt.

**Discarded draw:** the first completed draw (500-PR window, pre-amendment filters,
containing the two bot tasks) is preserved verbatim at
`audit/manifest-discarded-2026-08-01.json`. It was discarded for the reasons above,
not for its outcome; no run was ever executed against it. The authoritative manifest
is the post-amendment redraw with the same seed (20260801).
