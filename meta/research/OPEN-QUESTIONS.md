# ACE-100 open questions

Claims the standard makes, or could make, that no committed measurement
settles. Each entry is written as a falsifiable claim plus the measurement that
would settle it — an idea that cannot be written in that shape is not ready to
be here.

This register is development material: excluded from kit governance
(`.ace-ignore`) and from the release (`meta/publish.sh`). It carries no
commitment to run anything. Its purpose is to feed
`experiments/<id>/PREREGISTRATION.md`: a preregistration cites the `OQ-N` it
answers, and `docs/standard/changes.md` cites the `OQ-N` a rule closed.

Identifiers are stable. A closed question keeps its number and records what
closed it.

## Status values

| Value | Meaning |
|---|---|
| open | No measurement exists |
| registered | An experiment's preregistration names it |
| closed | A measurement settled it; the row says which |

## The register

### OQ-1 — Collocation against a linked document

**Claim.** For a fact true of one file, short collocated comment prose produces
higher task quality at lower total tokens than the same fact held in a
document the comment cites.

**Why it is open.** The token model favors fragmentation. A collocated comment
costs `C` on every visit; a linked document costs `0` when the fact is not
needed and `C + t` when it is, so fragmentation wins whenever the probability
of need falls below `C/(C+t)` — close to 1 for long prose and a cheap
retrieval. What the token model omits is the cost of a miss: an edit made
without the rationale is a quality failure, not a cost. Collocation also
carries two properties the model cannot price. The comment enters context
whether or not the agent chose to load it, and it travels in the diff, so it is
updated with the code or its staleness is visible at review. ACE 14.9's field
note records the opposite case: four conforming divisions left 101 stale paths.

**Measurement.** Two arms over the same tasks, differing only in whether
file-local rationale sits in comments or in cited documents. Report task
quality, total tokens, and the rate at which the cited document is opened when
it is needed.

**Note.** Issue 4 narrowed this question rather than answering it. See OQ-6.

**Status:** open.

### OQ-2 — The description as a follow signal

**Claim.** An agent deciding whether to open a cited document decides better
when it first reads that document's `description` (ACE 13.2) than when it
decides from the citation alone.

**Why it is open.** ACE 13.2 makes `description` mandatory on every governed
document, so every repository pays the write cost. Nothing measures the read
benefit. The alternative — copying the description to the citation site —
breaks ACE 14.7 and was rejected on that ground, not on evidence.

**Measurement.** Over tasks where a cited document is known to be needed, and
tasks where it is known not to be, report the rate of correct open and correct
skip with and without the description probe.

**Status:** open.

### OQ-3 — Probe before load

**Claim.** An agent that reads descriptions or a directory index before loading
documents reaches the same task quality with less context than an agent that
loads documents directly.

**Why it is open.** Section 19 states the protocol because ACE 13.2 and ACE
11.3 already pay for it, not because a measurement supports it. The protocol
may also lose facts: a probe that reads a description and skips the document
skips whatever the description does not name.

**Measurement.** Same tasks, two reading protocols, one corpus. Report task
quality, context tokens, and the rate at which a task-relevant fact was present
in the corpus and absent from the run.

**Status:** open.

### OQ-4 — The reader tool against a written command

**Claim.** `tools/describe.sh` costs fewer output tokens than the equivalent
hand-written probe, and removes the failure where a malformed command returns
nothing and the agent concludes the corpus is empty.

**Why it is open.** The saving is on the output side, which no ACE-100
measurement instruments today. The failure mode is asserted from reasoning, not
observed.

**Measurement.** Count output tokens spent on probe commands per run, with and
without the tool. Count runs where a probe returned nothing and the agent
proceeded as though the corpus held nothing.

**Status:** open.

### OQ-5 — Ranked search over a flat listing

**Claim.** Ranked or structured search over document descriptions improves
findability enough to justify a dependency the kit does not have today.

**Why it is open.** `tools/describe.sh` ships a flat listing with a pattern
filter, and `check.sh`'s zero-dependency property is load-bearing for adoption.
Anything richer costs that property.

**Measurement.** Experiment 2's RQ2 instruments findability. Add a search arm
and report accuracy and cost against the flat listing.

**Status:** open.

### OQ-6 — Does the 20-word limit transfer to comment prose

**Claim.** ACE 6.1's 20-word limit improves agent outcomes on comment prose as
it does on document prose.

**Why it is open.** This is the one entry that records a claim Issue 4 now
**enforces**. The limit was calibrated on reference documents. Applied to the
comment corpus of the field repository, it reports about 4,458 findings against
prose that reads as the best in that repository. Two readings fit that number:
the comments are wrong, or the limit does not transfer. Issue 4 chose the first
on judgment.

**Measurement.** Same tasks over a comment corpus rewritten to the limit and
one left as written. Report task quality and tokens.

**Status:** open.

### OQ-7 — One rule implementation or two

**Claim.** A tree-sitter extractor can replace `lint.py` rather than sit beside
it, and a single implementation of the ACE 8.5 to 8.8 count is achievable.

**Why it is open.** The count is subtle: a backticked span is one word, a
parenthetical counts once, a logical sentence spans line wraps. Two
implementations will disagree, and the disagreement appears as a file that
passes one checker and fails the other. Distribution compounds it. A native
binary costs the inspectability that `adopt.sh` relies on, and a bundled
library makes a runtime a kit dependency.

**Measurement.** Build the extractor, run both over one corpus, and count the
files where the verdicts differ.

**Status:** open.

### OQ-8 — Citation resolution

**Claim.** Checking that a stable identifier citation resolves catches more
real rot than checking that a path resolves.

**Why it is open.** In the field repository, comments carry 1,507 identifier
citations across 38 documents, 685 backticked paths, and no markdown links.
Issue 4 checks the paths and not the identifiers, which inverts the risk: ACE
15.2 divisions move paths and leave identifiers untouched, so the checked form
is the one that rots. The identifier form was cut because it needs a per-repository
declaration mechanism the kit does not have.

**Measurement.** Over a repository's history, count citations that became
unresolvable, by form.

**Status:** open.

### OQ-9 — Does file-level exemption over-exempt

**Claim.** A file-level `ace-exempt` declaration disables rules across more
prose than the deviation needs, often enough to justify a line-level form.

**Why it is open.** Issue 4 chose file-level to match ACE 13.7, which is
per-document, and to keep ACE 17.7's ledger row affordable. A line-level form
would demand a ledger row per line, which either buries the ledger or gets
dropped. Adding granularity later is cheap, and removing it is not.

**Measurement.** Count declarations in an adopting repository, and for each,
count the lines the rule was disabled over against the lines that needed it.

**Status:** open.
