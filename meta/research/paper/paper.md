# Does a Documentation Standard for LLM Agents Pay for Itself? A Pre-Registered Evaluation of ACE-100

**Owen Delahoy** · **Claude Fable 5 (Anthropic)**†
*Self-published preprint. Experiment 1 of 2; Experiment 2 sections are marked
as pending.*

†AI system, credited as a co-author at the human author's invitation; see
the Contributions statement for what it did and where accountability rests.

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
success threshold of ≤0.80. **H2 is not established, but its failure is narrow
and one-sided**: the blinded Opus-5 judge scored ace within the 0.5-point
margin of original on all three rubric dimensions (correctness +0.12,
completeness −0.17, convention +0.08), and suite-pass met its margin at point;
only reference-tests (Δ −12.5pp) missed — and §7 shows that component is
confounded by differential access to the reference solution. The mechanism
data explain the cost result:
migration *grew* the corpus 14% (253K → 290K tokens) and roughly doubled the
file count, agents in every arm read only ~1.6–1.7K explicit documentation
tokens per run through ad-hoc shell commands rather than the kit's intended
navigation structure, and the no-docs ablation matched the documented arms on
functional tests for four of six tasks — and once leakage-affected runs are
removed, for every task. On this repository and task mix the documentation is
barely load-bearing, so there is nothing for a documentation-efficiency
standard to save. Corpus size does not cleanly predict cost either: ace costs
1.159× the naive control on 5 of 6 tasks while carrying a 7.8% *smaller*
corpus. A post-hoc turn analysis finds the ACE-100 arm running ~12 turns
longer than that control on 6 of 6 tasks, but we report it as an open
question rather than a result: it is one of 64 interval tests of which ~3
false positives are expected, and no mechanism survives scrutiny. Migration
cost $116.45 and, with negative per-run savings, never breaks even. We report two protocol
deviations found by our own audit — Bash-level outbound network access
survived the registered "network off" claim, and a registered strong-model
side-measurement was not conducted — and publish the full audit trail,
including the instrument corrections the audit forced (Amendment 5). A
complete, adversarially verified sweep found reference-solution exposure in
28 of 96 runs (agents fetched the task PR's own diff, or reached the merged
fix through the clone's git history). The negative cost result survives their
removal (ratio 1.233, CI [1.062, 1.579], over the five tasks that retain a
clean baseline); the apparent quality deficit does not, and neither does the
measured value of documentation itself.

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
and its six amendments ship with this paper's repository; the amendment
story is told in full in §4, including the audit that overturned our own
measurement instrument (Amendment 5).

**Findings.** The headline result is negative and the mechanism is
instructive. ACE-100 migration made agent runs ~17% *more* expensive at the
task median, not ≥20% cheaper (H1). Quality was not non-inferior under the
strict registered rule (H2), but the blinded judge found ace within margin of
original on all three rubric dimensions and the single functional miss is
leakage-confounded — the negative verdict is real but narrow. Three
observations frame the cost result, none of them a demonstrated mechanism:
(i) migration grew the corpus rather than shrinking it — governed front
matter, indexes, and file splits added 14% in tokens and doubled the file
count, though corpus size does not by itself track cost across the arms;
(ii) agents consumed documentation in the ~1.6–1.7K-token range
per run regardless of arm, mostly through `grep`/`cat`/`sed` over files they
discovered ad hoc — the architecture's routing surface (indexes, CLAUDE.md
imports) was largely bypassed; and (iii) a no-docs ablation held functional
quality for most tasks — and for every task once leakage-affected runs are
removed — locating this repository's real knowledge in its source, tests, and
the model's priors rather than its prose. A documentation
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
| **ace** | Docs migrated by the kit's own advertised path, performed once by Claude Opus 5 (205 files, 289,596 tokens; see §6.2†). |
| **naive** | Original docs rewritten in place by Claude Opus 5 to token-match the ace arm (103 files, 312,116 tokens; ratio to ace 1.078, inside the registered ±10% band); original file boundaries kept; no indexes, front matter, or ACE vocabulary. |
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
20% double-scored for reliability; arm labels and documentation-path tells
stripped from both diffs, request order shuffled); (3) descriptive
completion/turns/wall-clock. Judge reliability: exact agreement on the
double-scored subset was 0.95 (correctness), 0.90 (completeness), and 0.63
(convention); within-one-point agreement was 1.00, 1.00, and 0.95 — convention
is the noisiest dimension, as expected, but the arms are separated by less
than the double-scoring spread on it, so we lean on the test outcomes.

All comparisons are within-task; we report per-task medians, cost ratios and
quality deltas with hierarchical-bootstrap 95% CIs (tasks, then trials;
10,000 replicates; seed 20260801), estimation over p-values. Decision rules,
fixed in advance: H1 supported iff the task-median ace/original cost ratio
≤ 0.80; H2 supported iff quality deltas sit within 5pp (test-pass) and 0.5
rubric points, CIs permitting. Runs with infrastructure failures would be
excluded; there were none. All 96 runs enter the cost statistics
(intention to treat).

**Statistic discipline.** We add one convention after making the mistake it
prevents (§6.2): every arm-level comparison is reported on the registered
within-task statistic. Any other summary — arm means over runs, marginal
medians — is labelled as such in the same sentence and carries no comparative
claim on its own. Where the two disagree, both are shown and the registered
one governs.

## 4. Amendments and Deviations, In Full

Pre-registration only means anything if the changes are public. Six
amendments were committed. The five that touch the experiment were each
committed before the step they affect; the sixth is post-hoc bookkeeping —
it records a repository-layout change made after all analysis was complete
and verified to leave every number identical. Two deviations were found
after the fact by our own audit and are disclosed here rather than amended
away.

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
4. **Amendment 4** — the nodocs ablation added after 43+ of the 72 registered
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

6. **Amendment 6** — the research tree was split into shared tooling
   (`meta/research/lib`) and per-experiment data
   (`meta/research/experiments/<id>`), and generated artifacts now record the
   tooling commit that produced them (§10). Made after all analysis was
   complete; re-running the analysis under the new layout reproduced every
   artifact identically, so the change is inert with respect to results.

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

Turn counts move with cost: by per-task *median*, the ace arm took more turns
than original on five of six tasks (e.g. pr-14690: 48 vs 33; pr-14461: 60 vs
47) — though §6.2 shows that difference does not survive interval estimation. The nodocs condition — descriptively — was the *most* expensive
(2.441), consistent with documentation having some navigational value that
deletion forfeits, while none of the documented arms converted that value
into savings over one another.

### 5.2 H2 — quality non-inferiority: not established; evaluable components lean negative

| component | margin | Δ (ace − original) | 95% CI | point | CI |
|---|---|---|---|---|---|
| suite pass | 5pp | −4.2pp | [−16.7, 0.0] | met | not met |
| reference tests | 5pp | −12.5pp | [−41.7, +8.3] | not met | not met |
| judge correctness | 0.5 | +0.12 | [−0.29, +0.54] | met | met |
| judge completeness | 0.5 | −0.17 | [−0.79, +0.46] | met | not met |
| judge convention | 0.5 | +0.08 | [−0.35, +0.54] | met | met |

Four of the five components meet their margin at the point estimate; the
lone failure is reference-tests. Suite regressions were rare everywhere
(ace 95.8% vs original 100%). The **blinded judge separates the arms by
almost nothing** on subjective quality: ace and original sit within 0.17
rubric points on every dimension, and the CIs straddle zero. Delivered
behavior — the reference PR's tests against the agent's implementation — is
the one axis where the arms diverge: ace 62.5% vs original 75.0% mean
per-task pass rate. The entire gap comes from one task — pr-14985, where ace
scored 25% against original's 100%; on the other five tasks the ace-original
reference-test delta is exactly zero (pr-15495 is 0% in both arms, so it
contributes nothing to the gap despite naive reaching 75% there). The registered rule requires
*every* component within margin, so the verdict is **not established** — but
the shape matters: the standard did not degrade judged code quality, and its
one measured functional deficit is exactly the component §7 shows is
confounded. With flagged runs removed, the ace-vs-original reference-tests
delta is 0.0pp (§7.2); the deficit against *naive* is unaffected by that
correction. Completion was 100% in every condition; wall-clock tracks turns.

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
a typical run's multi-million-token cache-read footprint — and closely
similar across the documented arms (we report no interval on this descriptive
quantity, so "similar" is an observation, not a test). Agents overwhelmingly reached
documentation through ad-hoc shell commands (`grep`/`sed`/`cat`, often below
a `cd`, through `git diff`, even `xargs` sub-shells) rather than the kit's
routing surface. The ace arm shows slightly *higher* contact frequency
(21/24 runs) and higher ambient tokens (its governed CLAUDE.md closure is
larger) — the architecture succeeded in being found, and still had no
lever: there was almost no reading for it to make cheaper.

### 6.2 The corpus grew — but corpus size is not what cost money

**What grew, and why.** Migration took 253,161 tokens in 103 files to
289,596 tokens in 205 files (+14%).† The composition is not what the design
assumed. Of the 103 files present in both arms, ace's prose is 72% of the
original's by character count and shrank in 73 of them; the governed YAML
front matter on those files adds 25,063 characters — 3.6% of their original
bytes, averaging 288 characters across the 87 that carry one. **Shared files
are 25% smaller even carrying their headers**, so front matter is not what
inverted the compression premise. (Across the whole migrated corpus, front
matter totals 47,922 characters in 189 of 205 files: 6.8% of the original
corpus, still far short of the growth.) The growth comes from 102 *new*
files (262,297 characters): the splits and indexes. And much of the apparent
shrinkage is relocation rather than compression — `docs/coding-guidelines.md`
went from 38,716 to 3,051 characters because it became a router, its body
moving into `docs/coding-robustness.md`, `docs/coding-modules.md`, and
siblings. Same prose, new addresses.

**Corpus size does not cleanly predict cost.** The registered statistic is the
within-task cost *ratio* (§7 of the pre-registration), and under it the three
pairwise comparisons do not line up with corpus size. ace costs 1.172×
original with a 14% larger corpus, and naive costs 1.071× original with a 23%
larger one — both consistent with size mattering. But **ace costs 1.159×
naive (5 of 6 tasks) while carrying a corpus 7.8% *smaller***, which size
cannot explain. Whatever separates ace from its matched control is not the
number of tokens on disk. That is unsurprising given §6.1: agents pulled
~1.6–1.7K explicit documentation tokens per run out of a 250–312K-token
corpus, so the corpus barely touches the context window and cannot move the
bill by itself.

*A caution about statistics, since we tripped over it ourselves.* An earlier
draft of this section argued the stronger claim that corpus size and cost are
*anti-correlated*, on the basis that naive has the largest corpus and the
lowest mean per-run cost ($2.07 against ace $2.54 and original $2.44). Those
means are unweighted over 24 runs each and are not the registered statistic;
they are dominated by pr-14985, the most expensive task, where all four
original-arm runs are leakage-flagged (§7). Dropping that one task inverts the
ordering. We report the within-task ratios above and flag the discrepancy
rather than bury it: arm-level means and the registered within-task statistic
disagree here, and only the latter is licensed.

**Cost is turns.** Per-run cost is close to linear in turn count: dollars per
turn are near-constant across conditions (original 0.0368, ace 0.0363, naive
0.0359, nodocs 0.0383), correlation between turns and cost across all 96 runs
is 0.878, and cache-read — re-sending the accumulated conversation each turn —
is 67–70% of every arm's bill. "Why did an arm cost more" therefore reduces
to "why did it take more turns."

**One turn difference is suggestive; none is conclusive.** Turn differences,
within-task paired with the registered seed and hierarchical bootstrap
(post-hoc; see the multiplicity caveat below):

| comparison | Δ mean turns | 95% CI | tasks with Δ>0 |
|---|---|---|---|
| ace − original | +3.42 | [−11.12, +15.50] | 4 of 6 |
| **ace − naive** | **+12.25** | **[+3.58, +23.04]** | **6 of 6** |
| naive − original | −8.83 | [−27.29, +4.46] | 3 of 6 |
| nodocs − original | +3.83 | [−11.58, +18.54] | 4 of 6 |

(Deltas are of per-task *mean* turns; §5.1's "five of six" counts per-task
*medians*. That the sign count moves with the choice of statistic is itself a
measure of how little separates these two arms.)

The headline comparison against original does **not** resolve — we cannot
claim ACE-100 runs take more turns than original-docs runs. The ace-vs-naive
difference does, at ~12 turns per run and positive on every task. Because
naive is rewritten prose at ace's token count with no front matter, indexes,
or splits, that pair would isolate the *document architecture* from corpus
size and from mere rewriting. We report it as suggestive rather than
established, for two reasons.

**Multiplicity.** This decomposition runs 64 interval tests (four pairwise
comparisons × one total plus fifteen categories). Four excluded zero;
**3.2 are expected by chance at α = 0.05.** The hit count is the same order
as the false-positive rate, and the hits are scattered incoherently across
unrelated pairs and categories — the signature of multiplicity rather than
mechanism. We therefore treat all three *category-level* exclusions as noise,
including `test` in the ace-naive comparison. For the primary family of four
total-turn comparisons, ace-vs-naive survives Bonferroni adjustment
([+1.42, +26.00] at the family-adjusted level, bootstrap mass at or below
zero 0.19%, sign test on 6/6 tasks p = 0.031); it does not survive adjustment
over all 64 tests ([−1.38, +31.92]). Which correction is appropriate is a
judgment call — the category tests are secondary to the primary family — and
readers who prefer the conservative reading should treat the turn result as
unresolved along with everything else.

**Noise floor.** Run length is extremely variable. The mean coefficient of
variation of turn count *within* a (task, arm) cell — same task, same
documentation, four trials — is **0.22**, and individual cells range from 27
to 58 turns (pr-14461/original) and 106 to 175 (pr-14985/original). A
12-turn arm difference across six tasks sits close to that resolution limit.

**No mechanism identified.** We classified every tool-use round in all 96
runs into fifteen activity categories (turn accounting is exact: `num_turns`
= tool-use blocks + 1 on all 96 runs, zero parallel tool-use messages), and
the gap does not localize: all 14 categories with a non-zero difference point
the same way, with the ace arm doing more of each. The two mechanisms we
would have predicted both fail. *Fragmentation* — 205 files instead of 103,
indexes routing to splits — predicts the gap in documentation navigation, but
doc-reads contribute only +0.29 of the +12.25, because agents barely read
documentation at all (§6.1) and there is little to fragment. *Ambient
instruction load* — the migrated `CLAUDE.md` is 422 characters against the
original's 11 — fails because that file is only a pointer: the instructions
it imports (`AGENTS.md`) are equivalent across arms (2,572 / 2,763 / 2,952
characters, same rules).

Nor is it clear the ace arm is the anomaly. Three conditions cluster tightly
in mean turns — original 66.5, ace 69.9, nodocs 70.3 — while **naive alone
sits at 57.6**. Read that way, the finding is less "the standard's
architecture is expensive" than "the naive rewrite was unusually efficient,"
which would be a result about verbose self-contained prose in a familiar file
layout rather than about ACE-100 at all. Amendment 3 already records that the
naive arm came out an *expansion* of the original (312,116 against 253,161
tokens) in the original file boundaries. We cannot distinguish these
readings, and we flag the question rather than answer it (§9).

*This subsection's turn analysis is **post-hoc and exploratory**. It was not
registered, it is not an H1/H2 readout, and it was added after the registered
analysis was complete; its hypotheses were generated after seeing the data.
It is reported because the question it raises is worth posing, not because
this experiment answers it. Tool, multiplicity accounting, and full output:
`meta/research/lib/classify_turns.py`,
`experiments/exp1/analysis/turn-decomposition.json`.*

†The gate artifact `audit/arm-gates/measure.json`, generated ten minutes
before the first run, records 289,596 tokens for ace; Amendment 3 recorded
289,575, measured before the final preservation-repair pass. The 21-token
difference (0.007%) is left uncorrected in the registered text and noted
here.

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

Read intention-to-treat, deleting every documentation file cost functional
quality on exactly two of six tasks (mean docs-value +8.3pp on reference
tests, +4.2pp on the suite). For four tasks the knowledge the agent needed
lived in source, tests, and model priors — the last being the registered
training-data-contamination threat: this repository's documentation is
plausibly in the subject model's pretraining corpus, diluting any in-repo
docs manipulation.

**That positive signal does not survive the leakage sweep, and the honest
reading is that it was never there.** Both tasks carrying non-zero docs value
are exactly the tasks where reference-test passes came from
reference-solution exposure: on pr-14985, **all 8** reference-test passes
across all arms are in class-(c) flagged runs, and on pr-15307, **all 7** are.
Neither task has a single clean pass in any arm. Removing flagged runs per
Amendment 5 (§7.2) removes pr-14985 from the comparison entirely — every
original-arm run there is flagged — and drives mean docs-value from **+8.3pp
to −6.7pp**, with four of the five surviving tasks at exactly zero and
pr-15495 at −33pp. On the clean subset, deleting the documentation did not
measurably cost functional quality anywhere.

This strengthens rather than weakens the section's conclusion: the
documentation is *even less* load-bearing than the intention-to-treat numbers
suggest. But it disqualifies the two examples we would otherwise have reached
for, and it is why no causal account of pr-14985 appears below.

The blinded judge tells the complementary half of this story. Where
functional tests barely separated the documented arms from nodocs, the
*judge* did: nodocs is the worst-scored arm on all three dimensions
(correctness 3.88, completeness 3.58, convention 3.62) versus 3.83–4.35 for the
three documented arms, with the largest gap on convention adherence — exactly
the MUST-level prose conventions (§3.2) that source code cannot convey.
Documentation on this repository buys *judged* quality, especially
convention-following, more reliably than it buys test-pass. That is a point
in the standard's favor at the margin — but it accrues to *having*
documentation, not to ACE-100 over the original or naive text: every
ace-vs-naive judge delta is ≤ 0.06 points with a CI spanning zero, so the
three documented arms are not separated on any dimension.

Two cautions on that judge reading. It rests on the nodocs arm, which
Amendment 4 registers as descriptive and exploratory, and on the judge, which
§3.4 places second in the quality hierarchy and whose convention scoring is
the noisiest dimension (0.63 exact agreement). We offer it as the more
suggestive half of a weak signal, not as a finding.

Earlier drafts of this section attributed pr-14985's ace-and-naive drop
(100% → 25%) to condensation loss surviving the Amendment-3 repair rounds.
That attribution is withdrawn: §7.2 shows the 100% original baseline is
itself produced by solution fetching, so the contrast is not evidence about
documentation quality at all. Documentation value here is small,
task-idiosyncratic, sign-unstable, and — once leakage is removed —
indistinguishable from zero. That is a hostile substrate for any
documentation standard to show gains on, and the central external-validity
caveat of this experiment (Experiment 2 targets a docs-load-bearing setting
for exactly this reason).

### 6.4 Value retention (Amendment 4 readout)

Where the floor is nonzero, retention(arm) = (arm − nodocs)/(original −
nodocs). Intention-to-treat, three tasks qualify: pr-14985 ace −0.5, naive
−0.5 (both rewrites landed *below* the no-docs floor); pr-15307 ace 1.0,
naive 1.0; and pr-15495, whose docs value is *negative* (−25pp, so the
original docs were worse than none) giving ace 1.0 and naive −2.0 — a
retention ratio against a negative denominator, which is why we report it but
draw nothing from it.

**This readout does not survive the leakage sweep either.** Its denominator
is the same docs-value quantity shown above to be leakage-composed: with
flagged runs removed, pr-14985 leaves the comparison entirely and every
remaining task except pr-15495 has a zero denominator, leaving retention
undefined. Experiment 2 shares this readout and its slots are reserved in §9
— but the readout needs a substrate where docs value is non-zero *and*
clean, which is precisely what Experiment 1 failed to supply.

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
  spread across all six tasks and all four conditions (original 9, ace
  5, naive 6, nodocs 8 runs). Event classes across all runs: 107
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

- **H1 is robust.** The ace/original cost ratio moves from 1.172 [0.881,
  1.487] to **1.233 [1.062, 1.579]**. The negative cost verdict does not
  depend on any leakage-affected run. We do not read the higher point
  estimate as leakage having *masked* a worse result, because the two
  numbers are not computed over the same tasks: every original-arm run in
  pr-14985 is flagged, so that task drops out and the sensitivity ratio is a
  five-task comparison against the registered six-task one. The robustness
  claim is that the verdict survives, not that the effect grows.
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
tells survive scrubbing) and the judge is a Claude-family model scoring a
Claude subject's work; it is secondary to test outcomes by registered
hierarchy, and convention scoring in particular is noisy (0.63 exact
agreement). Training-data contamination dilutes the docs
manipulation (§6.3) and is irreducible for repositories with real PR
history. The network deviation (§7) weakens "in-repo docs were the only
documentation channel"; the sweep bounds it. Migration was performed by a
stronger model (Opus 5) than the subject (Sonnet 5) — a documented
asymmetry that, note, biases *toward* the standard. The registered Opus-5
side-measurement was not conducted. The corpus-size reframe (Amendment 3)
means naive-vs-original tests matched-size rewriting, not shortening.

## 9. Open Questions and Experiment 2

Experiment 1's sharpest limitation is its substrate: docs-value near zero
on most tasks (§6.3). Experiment 2 is registered separately
(`meta/research/experiments/exp2/PREREGISTRATION.md`) and targets tasks where
documentation is load-bearing by construction, sharing the value-retention
readout of §6.4. Its candidate set is committed; no further work has begun.

Three questions this experiment raised but could not answer are worth
stating as an agenda, because each is answerable by a study designed for it
and none is answerable by adding tasks to this one.

**Does documentation architecture change how long an agent works?** §6.2
found the ACE-100 arm running ~12 turns longer than the token-matched naive
control on 6 of 6 tasks, and could neither confirm it against multiplicity
nor explain it. The obstacle is power, not instrumentation: with a
within-cell coefficient of variation of 0.22 on turn count, separating a
~15% arm difference needs far more than six tasks. A study aimed at this
would fix one task family, vary *only* file granularity — the same prose at
one file, ten files, and an index-plus-splits tree — and run enough trials
to resolve the noise. Cost follows turns almost exactly (§6.2), so turn count
is the efficient thing to measure.

**Is verbose, self-contained prose the actually efficient form?** The naive
arm was built as a control for length, not as a candidate, and it
outperformed the migrated arm on the two axes we can compare within-task:
ace costs 1.159× naive (5 of 6 tasks) and runs ~12 turns longer (6 of 6),
despite naive carrying a 7.8% larger corpus, with judge quality
indistinguishable between them. We state this narrowly on purpose — arm-level
*means* tell a stronger story that the registered within-task statistic does
not support (§6.2), and the turn result does not survive full multiplicity
correction. But the direction is consistent across both measures, and the
practical advice it would imply — write thorough, self-contained documents
where readers expect to find them, rather than compressing or splitting
them — runs against the premise this standard was built on. It deserves a
direct, powered test rather than the incidental one it received here.

**How much do agents read documentation at all, and when?** Every arm here
consumed ~1.6–1.7K explicit documentation tokens per run against corpora of
250–312K (§6.1), overwhelmingly through ad-hoc shell commands rather than
any intended navigation surface. If that generalizes, documentation
standards aimed at agent efficiency are optimizing a channel that carries
almost no traffic, and the prior question is what would make agents read
more — not what to do with the tokens once they do.

<!-- EXP2-SLOT: design summary, results, cross-experiment synthesis. -->

## 10. Reproducibility and Artifacts

The research tree ships in the kit repository under `meta/research/`:

```
meta/research/
  lib/                      shared pipeline, used by every experiment
  experiments/exp1/         this experiment: registration, config, manifest,
                            audit trail, analysis outputs
  experiments/exp2/         Experiment 2 (registered; not yet run)
  paper/                    this paper
  REPLICATION.md            step-by-step reproduction instructions
```

The pipeline is `select_tasks`, `build_arms`, `run_cell`, `evaluate`,
`docs_recount`, `extract_doc_reads`, `analyze`, `classify_turns`, and
`isolation_canary`. Tooling is shared across experiments and versioned
independently of the data it operates on; per-experiment settings (target
repository, seed, arms, corpus rule, caps, thresholds) live in
`experiments/exp1/experiment.json` rather than inside the tools.

**Every generated artifact names the tooling that produced it.** Each carries
a `provenance` block recording `tooling_commit` — the commit that last
modified `meta/research/lib` — plus the repository HEAD at run time and
whether the tooling tree was dirty. `tooling_commit` is the hash to check out
to reproduce that artifact; it is deliberately not HEAD, which moves whenever
anything is committed, including the artifact itself. An artifact produced
from an uncommitted tool change records `tooling_dirty: true` and is not
reproducible from a hash alone.

The Experiment 1 analysis reported here was produced at tooling commit
**`0e199e20cd33`**. To reproduce:

```sh
git checkout 0e199e20cd33
export ACE_EXPERIMENT_DIR="$PWD/meta/research/experiments/exp1"
# restore the published raw data into $ACE_EXPERIMENT_DIR/data/
python3 meta/research/lib/analyze.py
python3 meta/research/lib/classify_turns.py
```

Analysis is deterministic — seeded bootstrap, sorted keys, no timestamps in
the numbers — so `summary.json` and `turn-decomposition.json` reproduce byte
for byte once the `provenance` block (which carries a fresh timestamp) is
removed. Raw run data (96 transcripts, diffs, evaluation artifacts) is
published as a release asset; the repository stores the pointers and hashes.

Inference itself is nondeterministic at the API level. Replication is
therefore procedural (pinned models, commits, prompts, seeds), statistical
(distributions across trials rather than single runs), and data-level (every
transcript published). See `meta/research/REPLICATION.md` for the full
procedure, including the two environment variables that name the same clone
but are read by different tools.

## Contributions and AI disclosure

Owen Delahoy conceived the standard and the evaluation, wrote and registered
the pre-registration, directed every stage, and is accountable for the work.
Claude (Anthropic; Opus 5 and Fable 5 across sessions) built the pipeline
tooling, performed the arm migration and compression (as registered),
executed and audited the runs, revised and validated the consumption
instrument, ran the network sweep and analyses, and drafted this paper —
all under the pre-registration's constraints and the human author's review.
Final responsibility for claims, errors, and correspondence rests with the
human author.

Two reflexivity facts belong in the open: the subject agents, the migration
model, the audit agents, and the drafting assistant are all Claude-family
models — this paper is partly Claude analyzing Claude's behavior — and the
evaluated standard's authors ran its evaluation. The pre-registration,
fixed decision rules, adversarial verification layers, and full artifact
release are the mitigations; the negative headline result is perhaps the
strongest evidence they bound the incentives.

## Appendix pointers (generated from `audit/`)

- A. Preservation-gate rounds and residual flags (Amendment 3 closure).
- B. Doc-read audit: misattributions and missed events, verbatim
  (`audit/doc-read-audit.json`).
- C. Network sweep, all 96 transcripts (`audit/network-sweep.json`).
- D. Discarded task draw (`audit/manifest-discarded-2026-08-01.json`).
- E. Harness environment (`audit/harness-environment.json`).
- F. Migration ledger (`audit/arm-gates/migration-cost.json`).
