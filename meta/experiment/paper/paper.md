# Does a Documentation Standard for LLM Agents Pay for Itself? A Pre-Registered Evaluation of ACE-100

**Owen Delahoy**
*Self-published preprint. Experiment 1 of 2; Experiment 2 sections are marked
as pending. Draft — judge scores and the network-sweep appendix land in the
camera-ready data release.*

---

## Abstract

ACE-100 is a documentation standard for repositories worked on by LLM agents:
a controlled grammar, a compression discipline, and a document architecture,
adopted as a bundle on the premise that agents read documentation into a
limited context window, where excess text degrades work quality and raises
cost. We pre-registered that claim as two hypotheses — H1, agent runs on
ACE-100-migrated documentation cost at least 20% less than on the original
documentation; H2, their work quality is non-inferior — and tested them on
`open-telemetry/opentelemetry-collector` with six mechanically sampled
merged-PR tasks, four documentation conditions (original, ACE-100-migrated,
length-matched naive rewrite, and a no-docs ablation), and four trials per
cell: 96 agent runs under Claude Sonnet 5.

**H1 failed in the opposite direction**: the ACE-100 arm cost 1.172× the
original arm (task-median ratio; 95% CI [0.881, 1.487]), against a registered
success threshold of ≤0.80. H2's evaluable components lean negative
(suite-pass Δ −4.2pp, CI [−16.7, 0.0]; reference-tests Δ −12.5pp, CI [−41.7,
+8.3]; blinded judge pending). The mechanism data explain the cost result:
migration *grew* the corpus 14% (253K → 290K tokens) and roughly doubled the
file count, agents in every arm read only ~1.6–1.7K explicit documentation
tokens per run through ad-hoc shell commands rather than the kit's intended
navigation structure, and the no-docs ablation matched the documented arms on
functional tests for four of six tasks — on this repository and task mix, the
documentation is barely load-bearing, so there is nothing for a
documentation-efficiency standard to save. Migration cost $116.45 and, with
negative per-run savings, never breaks even. We report two protocol
deviations found by our own audit — Bash-level outbound network access
survived the registered "network off" claim, and a registered strong-model
side-measurement was not conducted — and publish the full audit trail,
including the instrument corrections the audit forced (Amendment 5). A
complete, adversarially verified sweep found reference-solution exposure in
28 of 96 runs (agents fetched the task PR's own diff, or reached the merged
fix through the clone's git history); removing them *strengthens* the
negative cost result (ratio 1.233, CI [1.062, 1.579]) and erases the
apparent quality deficit, which concentrates in leakage-affected trials.

---

## 1. Introduction

Documentation written for humans is now read by machines. LLM coding agents
open READMEs and contributing guides in the middle of tasks, pay per token to
do so, and act on what they find. ACE-100 takes that seriously as a design
constraint: it prescribes a controlled grammar (short declarative sentences,
a restricted vocabulary), aggressive compression, and a document architecture
(front matter, indexes, one-topic-per-file splits) intended to let an agent
route to exactly the prose it needs and read nothing else. The kit's own
statement of purpose is the testable premise: *"LLM agents read documentation
into a limited context window. Excess text decreases the quality of their
work and increases cost."*

Standards like this are cheap to advocate and expensive to adopt. A
maintainer considering migration needs to know whether the bundle — not any
single ingredient — changes what agents actually spend and produce. That is
an empirical question, and answering it credibly required guarding against
our own incentives: the evaluators are the standard's authors. We therefore
pre-registered the hypotheses, thresholds, repository-selection criteria,
task-selection procedure, execution protocol, quality hierarchy, and analysis
plan before selecting a repository, and recorded every subsequent change as a
numbered amendment committed before the step it affects. The pre-registration
and its five amendments ship with this paper's repository; the amendment
story is told in full in §4, including the audit that overturned our own
measurement instrument (Amendment 5).

**Findings.** The headline result is negative and the mechanism is
instructive. ACE-100 migration made agent runs ~17% *more* expensive at the
task median, not ≥20% cheaper (H1). Quality moved in the wrong direction on
the evaluable components (H2; judge scores pending). Three observations
explain it: (i) migration grew the corpus rather than shrinking it — governed
front matter, indexes, and file splits added 14% in tokens and doubled the
file count; (ii) agents consumed documentation in the ~1.6–1.7K-token range
per run regardless of arm, mostly through `grep`/`cat`/`sed` over files they
discovered ad hoc — the architecture's routing surface (indexes, CLAUDE.md
imports) was largely bypassed; and (iii) a no-docs ablation held functional
quality for most tasks, locating this repository's real knowledge in its
source, tests, and the model's priors rather than its prose. A documentation
standard cannot save tokens that were never being spent.

**Contributions.** (1) A pre-registered, fully audited negative result on a
documentation standard for LLM agents, with the decision thresholds fixed
before data. (2) A four-condition design whose no-docs floor converts the
usual "did the agent read the docs?" manipulation check into a causal
value-of-documentation measurement. (3) A documentation-consumption
instrument for agent transcripts — all channels, arm-relative corpus
matching, adversarially audited attribution rules — with its full revision
history (§4, Amendment 5). (4) Migration economics with a break-even frame
maintainers can reuse. (5) A complete artifact release: transcripts,
per-run records, audit trail, and every analysis input.

## 2. The Artifact Under Test

ACE-100 (evaluated at release Issue 3) governs a repository's prose
documentation. Its three components, adopted as a bundle via the kit's
`adopt.sh --migrate` path:

- **Controlled grammar.** Short declarative sentences; a banned-word list;
  measurable style rules enforced by the kit's checkers (`tools/check.sh`).
- **Compression.** Rewriting toward minimal token count while preserving
  factual and procedural content.
- **Document architecture.** Machine-oriented front matter on every file,
  index documents, one-topic-per-file splits, and resolvable cross-references,
  so an agent can route to the smallest sufficient document.

The claim under test is the bundle's effect on agent cost and quality; the
control arm (§3) isolates the bundle from mere rewriting at matched length.
Component isolation within the bundle is registered as out of scope.

## 3. Design

### 3.1 Conditions

One repository, identical code, four documentation states:

| Condition | Construction |
|---|---|
| **original** | Repository at the pinned commit, docs untouched (103 files, 253,161 tokens). |
| **ace** | Docs migrated by the kit's own advertised path, performed once by Claude Opus 5 (205 files, 289,575 tokens). |
| **naive** | Original docs rewritten in place by Claude Opus 5 to token-match the ace arm; original file boundaries kept; no indexes, front matter, or ACE vocabulary. |
| **nodocs** | The documentation corpus deleted from the workspace (Amendment 4; descriptive/exploratory only). |

naive-vs-original measures rewriting at matched length; ace-vs-naive measures
what the standard's structure adds beyond that; ace-vs-original is the
adopter's comparison. The nodocs floor measures what the documentation is
worth at all: per-task docs-value = quality(original) − quality(nodocs).

Three registered gates preceded any run: the kit's checkers pass on the ace
arm; corpus token counts snapshotted with the naive arm within ±10% of ace;
and an LLM-judge semantic-preservation pass over both rewritten arms with
repair. The preservation gate did not converge — each judge pass flagged a
fresh sample from the effectively unbounded space of condensation losses
(574 → 132 → 36 → 71 across rounds) — so Amendment 3 closed it by fixed
point: three repair rounds, then full disclosure of the final pass's residual
flags in the appendix rather than unbounded repair that would have ratcheted
the ace text back toward the original and eroded the treatment.

### 3.2 Repository and task selection

Selection criteria were fixed before scouting (docs load-bearing per §3.3's
check; multi-package; merged-PR ground truth; cheap real test suite;
permissive license; 20–150 doc files). Forty candidates were scouted, the
top eight clone-inspected, and `open-telemetry/opentelemetry-collector`
chosen (Amendment 1): ~92 curated docs including MUST-level prose
conventions, 100 Go modules, ~1,775 merged PRs in 18 months, a
credential-free `go test` suite, Apache-2.0.

Tasks are merged PRs sampled mechanically: filters (recency, ≥2 files
touched, linked issue or self-contained description, 30–400 changed lines,
CI-passed, not documentation-primary), stratification by task type, seeded
sampling (seed 20260801), target six tasks. The first completed draw was
discarded and redrawn under Amendment 2 — bot-authored PRs (two renovate
version bumps) defeated the description filter's intent — with the discarded
draw preserved verbatim in the audit trail. **Temporal firewall:** the task
list was fixed before either rewritten arm was built, and the migration and
compression agents never saw it.

The six tasks: pr-14461, pr-14690, pr-14985, pr-15108, pr-15307, pr-15495
(feature additions, behavior changes, and configuration-integration work;
per-task metadata in the manifest).

### 3.3 Execution

Subject model Claude Sonnet 5, pinned, default effort, for all arms; headless
Claude Code via the Claude Agent SDK, versions pinned; fresh clone of the
arm's repository state per run, discarded afterward. Prompt = the task's
cleaned issue/PR description plus a fixed implement-this instruction,
byte-identical across arms; documentation is never mentioned. Caps: 200
turns, 45 minutes, $15 computed cost. 4 trials per (task × condition) cell,
cell order randomized and interleaved; collected 2026-08-01 (UTC). 96/96
runs completed with zero failures and zero cap hits; subject runs totaled
$233.81 at standard prices. Costs are computed from per-run token usage at
standard published prices, so reported numbers are stable over time.

The registered protocol stated "network off (no web search/fetch)". The
harness's WebFetch/WebSearch tools were disabled, but our audit later found
Bash-level outbound HTTP had not been blocked — §7 reports the deviation, its
sweep, and its blast radius. The registered side-measurement (two tasks
repeated under Claude Opus 5, two trials per arm) was **not conducted**; §4
lists it among the deviations and it remains open work.

### 3.4 Quality evaluation and analysis plan

Quality reads out in a fixed hierarchy: (1) test outcomes — the repository's
existing suite (regressions), and the reference PR's tests run against the
agent's implementation (delivered behavior); (2) a blinded LLM judge (Claude
Opus 5 via the Batches API; correctness / completeness / convention, 1–5;
20% double-scored for reliability) — **pending at this draft**; (3)
descriptive completion/turns/wall-clock.

All comparisons are within-task; we report per-task medians, cost ratios and
quality deltas with hierarchical-bootstrap 95% CIs (tasks, then trials;
10,000 replicates; seed 20260801), estimation over p-values. Decision rules,
fixed in advance: H1 supported iff the task-median ace/original cost ratio
≤ 0.80; H2 supported iff quality deltas sit within 5pp (test-pass) and 0.5
rubric points, CIs permitting. Runs with infrastructure failures would be
excluded; there were none. All 96 runs enter the cost statistics
(intention to treat).

## 4. Amendments and Deviations, In Full

Pre-registration only means anything if the changes are public. Five
amendments were committed, each before the step it affects; two deviations
were found after the fact by our own audit and are disclosed here rather
than amended away.

1. **Amendment 1** — repository choice recorded; training-data contamination
   added to the threats register.
2. **Amendment 2** — task-filter corrections (bot-PR exclusion, recorded
   selection window, cross-repo linked issues) and a **discarded first draw**,
   preserved verbatim in the audit trail. No run was ever executed against it.
3. **Amendment 3** — preservation-gate closure by fixed point after
   non-convergence (§3.1), and the corpus-size observation: migration *grew*
   the corpus 14%, so the token-matched naive arm is an expansion, not a
   compression, of the original. H1 is unaffected (it measures per-run agent
   cost, for which the kit's mechanism is routing, not corpus totals); the
   design assumption is corrected in place and reported.
4. **Amendment 4** — the nodocs ablation added after 43 of 72 registered
   cells had completed but before any evaluation or cross-arm analysis;
   descriptive only; H1/H2 unchanged. Also registered the all-channel
   docs-consumption recount superseding the collection-time counters.
5. **Amendment 5** — the consequential one. A per-run audit of all 96
   transcripts (six audit agents, findings archived in
   `audit/doc-read-audit.json`) found the consumption instrument
   undercounting and misattributing: matching against the original corpus
   manifest structurally missed the ace arm's ~100 migration-created files;
   grep output was attributed to files that never opened; a harness
   placeholder string was counted as content; compound-command output was
   attributed wholesale. Amendment 5 fixed the instrument (arm-relative
   matching, per-channel attribution rules, an audited supplement for
   laundered reads), disclosed the network deviation, registered the
   classification rules for the full-transcript network sweep **before the
   sweep ran**, and fixed the leakage-handling rule (intention-to-treat with
   an exploratory sensitivity analysis) **before the sweep results were
   known**.

**Deviations (disclosed, not amended).** (a) Network isolation was assumed
from the sandbox and not verified; Bash-level outbound HTTP worked (§7).
(b) The registered Opus-5 side-measurement was not run before collection
closed; it remains open and is excluded from all claims here.

## 5. Results: The Registered Readouts

### 5.1 H1 — cost superiority: not met, sign reversed

Per-run cost (USD, standard prices), medians of per-task medians:

| condition | median task-median cost | runs |
|---|---|---|
| original | 1.837 | 24 |
| ace | 2.077 | 24 |
| naive | 2.143 | 24 |
| nodocs* | 2.441 | 24 |

*nodocs is descriptive only (Amendment 4).*

The registered statistic, the task-median **ace/original cost ratio, is
1.172, 95% CI [0.881, 1.487]** — the ACE-100 arm ran ~17% more expensive at
point, and the CI excludes the registered 0.80 threshold entirely. The
decision rule fails at the point estimate and at the CI. The other
registered pairs: ace/naive 1.159 [0.962, 1.426]; naive/original 1.071
[0.726, 1.376]. Rewriting at matched length was roughly cost-neutral;
the ACE-100 bundle on top of it was not.

Turn counts move with cost: the ace arm took more turns than original on
five of six tasks (e.g. pr-14690: 48 vs 33 median turns; pr-14461: 60 vs
47). The nodocs condition — descriptively — was the *most* expensive
(2.441), consistent with documentation having some navigational value that
deletion forfeits, while none of the documented arms converted that value
into savings over one another.

### 5.2 H2 — quality non-inferiority: not established; evaluable components lean negative

| component | margin | Δ (ace − original) | 95% CI | point | CI |
|---|---|---|---|---|---|
| suite pass | 5pp | −4.2pp | [−16.7, 0.0] | met | not met |
| reference tests | 5pp | −12.5pp | [−41.7, +8.3] | not met | not met |
| judge (3 dims) | 0.5 | *pending* | — | — | — |

Suite regressions were rare everywhere (ace 95.8% vs original 100%).
Delivered behavior — the reference PR's tests against the agent's
implementation — is where the arms separate: ace 62.5% vs original 75.0%
mean per-task pass rate. The damage concentrates in two tasks: pr-14985
(ace 25% vs original 100%) and pr-15495 (both 0%, naive 75%). With six
tasks the CIs are wide; the registered verdict is simply **not
established**, with both evaluable point estimates on the wrong side.
Completion was 100% in every condition; wall-clock tracks turns.

One caution attaches to the point deficits: §7's sweep found that every
original-arm pr-14985 trial had downloaded the reference solution, and with
flagged runs removed the ace-vs-original deltas are 0.0pp (§7.2). The
deficit against *naive* is unaffected by that correction.

### 5.3 Migration economics: no break-even

The one-time migration (Claude Opus 5, four sessions, 398 turns) cost
**$116.45 at standard prices** ($129.15 as harness-billed). Per-run savings
(original − ace, task-median) are **−$0.25**: negative. **There is no
break-even run count; migration is a pure cost at observed prices.** For
adopters the frame still generalizes: at the registered ≥20% saving on this
repository's ~$1.84 task-median runs, migration would have paid back in
~317 runs.

## 6. Mechanism: Why the Standard Could Not Win Here

### 6.1 Agents barely read the docs — in any arm

The revision-2 consumption instrument (Amendment 5; all channels — Read
tool, Bash readers including `git show`/`diff`, Grep, subagent sidechains —
arm-relative corpus matching, audited attribution) measures what actually
entered each run's context from the arm's documentation:

| condition | explicit doc tokens/run (mean) | median | runs w/ contact | ambient (CLAUDE.md closure) |
|---|---|---|---|---|
| original | 1,720 | 534 | 18/24 | 645 |
| ace | 1,614 | 852 | 21/24 | 795 |
| naive | 1,713 | 659 | 18/24 | 739 |
| nodocs | 101* | 0 | 4/24 | 0 |

*nodocs events are all flagged: content under a doc path that did not exist
at run start (regenerated by `mdatagen` build tooling mid-run, plus one
audited solution-content exposure; §7).*

Explicit documentation contact is ~1.6–1.7K tokens per run — under 0.1% of
a typical run's multi-million-token cache-read footprint — and statistically
indistinguishable across the documented arms. Agents overwhelmingly reached
documentation through ad-hoc shell commands (`grep`/`sed`/`cat`, often below
a `cd`, through `git diff`, even `xargs` sub-shells) rather than the kit's
routing surface. The ace arm shows slightly *higher* contact frequency
(21/24 runs) and higher ambient tokens (its governed CLAUDE.md closure is
larger) — the architecture succeeded in being found, and still had no
lever: there was almost no reading for it to make cheaper.

### 6.2 The corpus grew

Migration's governed front matter, indexes, and splits took 253,161 tokens
in 103 files to 289,575 tokens in 205 files (+14%). The premise "compression
reduces what agents read" inverted at the corpus level; only routing could
have delivered savings, and §6.1 shows routing had nothing to route around.

### 6.3 The no-docs floor: this repository's docs are barely load-bearing

Reference-test pass rates per task, with the docs-value Δ(original −
nodocs):

| task | original | ace | naive | nodocs | docs value |
|---|---|---|---|---|---|
| pr-14461 | 100% | 100% | 100% | 100% | 0pp |
| pr-14690 | 100% | 100% | 100% | 100% | 0pp |
| pr-14985 | 100% | 25% | 25% | 50% | +50pp |
| pr-15108 | 100% | 100% | 100% | 100% | 0pp |
| pr-15307 | 50% | 50% | 50% | 25% | +25pp |
| pr-15495 | 0% | 0% | 75% | 25% | −25pp |

Deleting every documentation file cost functional quality on exactly two of
six tasks (mean docs-value +8.3pp on reference tests, +4.2pp on the suite).
For four tasks the knowledge the agent needed lived in source, tests, and
model priors — the last being the registered training-data-contamination
threat: this repository's documentation is plausibly in the subject model's
pretraining corpus, diluting any in-repo docs manipulation. Where docs
carried real value (pr-14985), *both* rewritten arms destroyed most of it
(100% → 25%) — a preservation failure that three repair rounds and
disclosure (Amendment 3) flagged but did not fully prevent — and on
pr-15495 the original docs were actively worse than nothing while the naive
rewrite helped. Documentation value here is small, task-idiosyncratic, and
sign-unstable — a hostile substrate for any documentation standard to show
gains on, and the central external-validity caveat of this experiment
(Experiment 2 targets a docs-load-bearing setting for exactly this reason).

### 6.4 Value retention (Amendment 4 readout)

Where the floor is nonzero, retention(arm) = (arm − nodocs)/(original −
nodocs): pr-14985 ace −0.5, naive −0.5 (both rewrites landed *below* the
no-docs floor); pr-15307 ace 1.0, naive 1.0. Experiment 2 shares this
readout; its slots are reserved in §9.

## 7. Protocol Deviation: Network Isolation and Solution Leakage

The registered protocol claimed network-off execution. In fact, only the
harness's web tools were disabled; the sandbox did not block Bash-level
outbound HTTP. Our transcript audit found working `curl` and `gh api` calls,
including retrievals that touch the task's own solution: the reference PR's
diff fetched from GitHub, and `git show` of the reference merge commit,
which the workspace clone's full history made locally reachable (a second,
offline leak channel the same audit surfaced). The complete sweep below
shows this was not rare.

Amendment 5 registered, before the sweep ran, a complete classification of
every outbound access in all 96 transcripts — (a) task-metadata lookup, (b)
external documentation retrieval, (c) reference-solution exposure, (d)
other — plus the same classification for git-history access to post-base
commits, and fixed the handling rule: no run is excluded from the registered
analyses; class-(c) runs are flagged; every registered readout is re-reported
with flagged runs removed as a clearly-labeled sensitivity analysis; judging
proceeds blind to the flags.

### 7.1 Sweep results

The sweep (a deterministic candidate pass over all 96 transcripts — 695
candidate events — then one classifier agent per task×condition cell, then
an adversarial verifier re-deriving every class-(c) claim and every
all-clear from the raw tool results; `audit/network-sweep.json`) found:

- **28 of 96 runs (29%) carry class-(c) reference-solution exposure**,
  spread across five of six tasks and all four conditions (original 8, ace
  5, naive 7, nodocs 8 runs). Event classes across all runs: 107
  metadata lookups, 21 external-documentation retrievals, 124
  solution-exposure events, 128 other (mostly Go module-proxy downloads).
- The exposure channels are blunt: agents `curl`ed the task PR's own
  `.diff` from GitHub (pr-14985, pr-15108, pr-15307), fetched
  fix-describing PR bodies and commit messages via the API, ran `git show`
  / `git log -p --all` on the reference merge commit that the workspace
  clone's full history made locally reachable — and, in one nodocs run,
  **`git cherry-pick -n`ed the reference commit and submitted it as the
  answer** (pr-15495/nodocs/trial-3).
- **Zero access to hosted opentelemetry.io documentation anywhere** — the
  deviation did not open a treatment-relevant documentation channel; §6.1's
  in-arm consumption numbers exclude web content by construction.

### 7.2 Sensitivity analysis (exploratory)

With the 28 flagged runs removed (analysis Table 8):

- **H1 is robust — indeed stronger.** The ace/original cost ratio moves
  from 1.172 [0.881, 1.487] to **1.233 [1.062, 1.579]**: the CI now
  excludes even parity. The negative cost verdict does not depend on any
  leakage-affected run.
- **The observed H2 point deficits do not survive.** Ace-vs-original
  quality deltas collapse to 0.0pp (suite and reference tests) on the five
  tasks with unflagged original-arm trials. The registered deficit
  concentrates in pr-14985 — where *all four* original-arm trials had
  fetched the actual solution and scored 100%, against ace's 25% with one
  flagged trial. The honest reading: the ace-vs-original quality gap in
  §5.2 is confounded by differential solution-fetching, not evidence of
  docs-caused degradation; the registered verdict ("not established")
  stands, and the ace-vs-naive deficit (−12.5pp [−41.7, 0.0]) remains on
  all six tasks.

The registered intention-to-treat results remain the headline numbers;
this section is the bound on what the deviation could have moved.

## 8. Threats to Validity

Single repository; six tasks; a single primary subject model; wide CIs by
design honesty (estimation over hypothesis tests, hierarchical bootstrap
over a small task sample). The evaluators are the standard's authors —
mitigated by pre-registration, mechanical selection, the temporal firewall,
fixed decision rules, and this paper's disclosure of its own negative
result and instrument failures. LLM-judge blinding is imperfect (doc-style
tells survive scrubbing); judge results are pending and secondary by
registered hierarchy. Training-data contamination dilutes the docs
manipulation (§6.3) and is irreducible for repositories with real PR
history. The network deviation (§7) weakens "in-repo docs were the only
documentation channel"; the sweep bounds it. Migration was performed by a
stronger model (Opus 5) than the subject (Sonnet 5) — a documented
asymmetry that, note, biases *toward* the standard. The registered Opus-5
side-measurement was not conducted. The corpus-size reframe (Amendment 3)
means naive-vs-original tests matched-size rewriting, not shortening.

## 9. Experiment 2 (Pending)

Experiment 1's sharpest limitation is its substrate: docs-value near zero
on most tasks (§6.3). Experiment 2 is registered separately
(`meta/experiment2/PREREGISTRATION.md`) and targets tasks where
documentation is load-bearing by construction, sharing the value-retention
readout of §6.4. Its candidate set is committed; no further work has begun.

<!-- EXP2-SLOT: design summary, results, cross-experiment synthesis. -->

## 10. Reproducibility and Artifacts

The experiment tree ships in the kit repository under `meta/experiment/`:
the pre-registration with all five amendments; the pipeline
(`select_tasks`, `build_arms`, `run_cell`, `evaluate`, `docs_recount`,
`extract_doc_reads`, `analyze`); the task manifest with the discarded
draw; arm-construction gates (checker output, token measurements, all
preservation rounds, the migration ledger); the doc-read audit; and the
analysis outputs. Raw run data (96 transcripts, diffs, evaluation
artifacts) is published as a release asset; the repository stores the
pointers. Inference is nondeterministic at the API level; replication is
procedural (pinned models, commits, prompts, seeds), statistical
(distributions across trials), and data-level (every transcript published).

## Appendix pointers (generated from `audit/`)

- A. Preservation-gate rounds and residual flags (Amendment 3 closure).
- B. Doc-read audit: misattributions and missed events, verbatim
  (`audit/doc-read-audit.json`).
- C. Network sweep, all 96 transcripts (`audit/network-sweep.json`).
- D. Discarded task draw (`audit/manifest-discarded-2026-08-01.json`).
- E. Harness environment (`audit/harness-environment.json`).
- F. Migration ledger (`audit/arm-gates/migration-cost.json`).
