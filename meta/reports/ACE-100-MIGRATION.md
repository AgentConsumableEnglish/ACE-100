# ACE-100 Issue 1 — a migration report

Feedback for the authors of the ACE-100 kit, from one full adoption.

**This document is deliberately not written in ACE-100**, and is excluded from the repository's
conformance sweep. Part of what follows is that ACE-100 cannot express an argument of this shape:
it has no modality for the counterfactual ("a smaller core *would* have…"), and its 250-word
ceiling would divide a single line of reasoning across six files. That limitation is itself a
finding, so demonstrating it seemed more useful than hiding it.

> **Status: answered.** ACE-100 Issue 2 (2026-07-31) acts on this report and cites it as the source
> of each change. This repository migrated to Issue 2 on 2026-08-01
> ([ADR-0043](docs/adr/0043-the-controlled-language-moves-to-issue-2.md)). The report below is kept
> exactly as written — it is the evidence behind those changes, and revising it after the fact
> would destroy what it is for. What each of its seven suggestions produced:
>
> | Suggestion | What Issue 2 did |
> |---|---|
> | 1. Split the vocabulary | ACE 1.1 is two layers: a closed function core of ~130 words, an open content layer under style rules |
> | 2. Ship a conformance checker | `tools/check.sh` and `tools/lint.py`. The kit adopted *this repository's* checker, credited in its header |
> | 3. Make ACE 15.1 deterministic, or drop its (M) | One count: 120 body lines, everything included. ACE 8.7's second count is repealed, ACE 8.8 demands one total, and the table escape is closed |
> | 4. State the division shape canonically | ACE 15.2 is now that shape: `topic.md` becomes `topic/README.md`, plus its parts |
> | 5. Add a counterfactual modality | ACE 3.7 permits `would` for a condition that is not real |
> | 6. Add a migration chapter | Section 18, seven rules, drawn from the failures below |
> | 7. Reconsider what the size limits optimize | ACE 15.5 states the priority order, and ACE 15.1 gained a section that argues the trade rather than asserting it |
>
> The reported defects are fixed too: the dictionary reaches Z and holds `ZERO`; ACE 15.3 no longer
> breaks ACE 9.2; ACE 13.8 warns that front matter breaks head-parsers; ACE 10.6 makes embedded
> structured data verbatim; ACE 12.5 gives a rule document its own genre; and ACE 6.1 now binds
> inside a `HowTo`.
>
> **One request was answered differently.** This report asked for a *declared index name per
> directory*, to spare an adopter the churn of renaming `INDEX.md`. ACE 11.3 is unchanged. Instead
> ACE 14.8 protects any load-bearing path and ACE 13.7 declares the exemption — which answers the
> history-orphaning half of the complaint and not the naming half.
>
> What this repository still does not obey is in
> [the deviations ledger](docs/standard/deviations.md).
>
> **There is a second report.** A later pass closed the linter findings that Issue 2 first made
> visible, and wrote up what it learned:
> [ACE-100 Issue 2 — a second field report](ACE-100-FIELD-REPORT-2.md). Its headline is that every
> `(M)` rule with a shipped checker was at zero, and every `(M)` rule without one had silently
> rotted — 99 documents naming a parent that does not exist, 159 decision-record parts that lost
> their genre, 101 dead paths. The two-layer vocabulary of suggestion 1, meanwhile, held completely:
> that pass needed no new word, term or ban.

## What was migrated

A TypeScript monorepo — a local-first document application with sync, an assistant, and a
blockchain-corpus feature. Documentation was already taken seriously here: architecture decision
records, a domain model, agent-facing procedure docs, and a markdown issue tracker.

| | |
|---|---|
| Source documents | 227 |
| Source lines | 17,425 |
| Largest document | 917 lines |
| Documents over the 80-line limit | 57 |
| Resulting documents | ~1,800 |
| Rewritten by | ~30 parallel LLM agents, one batch each |

Every governed document was rewritten: the `docs/` tree, the root instruction files, the app
READMEs, and 173 files of in-flight specs and tickets. Excluded: vendored third-party skills, and
the kit itself.

## The headline: ACE 1.1 does not survive contact

**The closed vocabulary is the rule this repository could not obey, and we do not believe any
real codebase can.**

The 587-word core was measured against the corpus by every batch independently. The counts are
distinct word forms outside the core, the declared technical terms, and the `-ing` allowlist:

| Area | Unapproved forms |
|---|---|
| Sync and sharing | ~1,150 |
| Domain model | 796 |
| First screen and profiles | 775 |
| Inline objects | ~700 |
| Build failures | 573 |
| Space sharing | 554 |

These are not exotic words. The gaps that recurred across every single batch were ordinary
English: `already`, `still`, `either`, `neither`, `nothing`, `instead`, `rather`, `behind`,
`beside`, `inside`, `way`, `place`, `ask`, `say`, `exist`, `carry`, `land`, `kind`, `shape`,
`whether`, `enough`, `twice`, and most number words above three.

We used the standard's own escape (ACE 1.11, `add-a-word.md`) and added **18** words after
reviewing 572 ranked candidates. The restraint was deliberate: 556 were rejected, the large
majority because an approved word already carried the concept and `add-a-word.md`'s CAUTION
against synonyms is correct and load-bearing. The vocabulary ended at 605 words. It was not close
to enough.

The escape hatches do not close the gap:

- **Backticks (ACE 1.5)** are correct only for identifiers. Backticking `already` would be a lie.
- **Technical terms (ACE 1.6)** are restricted to "a name for a real thing". `already` is not a
  name for a real thing. Agents under pressure will widen this until `technical-terms.md` is a
  second dictionary — we watched it grow from 17 rows to 188 in one session, and that was *with*
  explicit instructions not to abuse it.

**The prediction we would make:** every adopter either silently breaks ACE 1.1, or inflates the
technical-terms table until the vocabulary is open in fact and closed only on paper. We chose to
break it openly and document it, which at least leaves the next reader an honest signal.

**Suggestion.** Split the vocabulary into a *closed function core* and an *open domain layer*.
The function words — determiners, conjunctions, prepositions, modals, quantifiers, pronouns — are
where controlled language earns its keep, because that is where ambiguity lives. Nouns and verbs
of a domain are where it fails, and where the cost of policing is highest for the least benefit.
ASD-STE100 works because aerospace maintenance has a bounded object vocabulary. Software does not.

## Contradictions inside the standard

These are not edge cases; each one was hit repeatedly by independent agents.

**ACE 15.1/15.2 against ACE 15.5 and 14.7.** The size limits force division. ACE 15.5 forbids a
division that makes a reader open three documents for one question. ACE 14.7 forbids repeating a
fact to prevent that. For any document with interlocking content, all three cannot hold. A real
example: one ticket had thirteen acceptance criteria. They do not fit in 250 prose words. Divided,
"what are this ticket's criteria" now costs three documents — precisely the failure ACE 15.5
names. There is no conforming answer.

We resolved it by giving ACE 15.5 priority, but the standard should say so rather than leaving
every author to rediscover the conflict.

**ACE 8.5 and 8.7 make ACE 15.1 uncomputable, and ACE 15.1 is marked (M).** Parenthetical text
counts once inside its sentence and again as its own sentence; quoted text, headings, and
hyphenated groups each count as one word. The same characters are counted twice. No two readers
and no two linters will agree on "250 prose words", yet the rule is mandatory — which implies a
machine can decide it. We had to fix an arbitrary interpretation in our checker to make the number
mean anything at all.

**Tables are an unpriced loophole, and every agent found it.** ACE 15.1 excludes tables from the
prose count. Faced with a 600-word document and a 250-word ceiling, the reliable move is to convert
prose to a table — which we did, agents did, and this report does. Content is preserved and the
rule is satisfied, but the rule stops measuring anything. If the limit is about an agent's reading
cost, a 60-row table is not cheaper than the paragraph it replaced.

**ACE 12.1 and 12.3 have no type for a rule reference.** A document that both states a rule and
tells a reader to obey it — which describes most agent-facing documentation, and the kit's own
rule files — mixes description with procedure. `TechArticle` binds to Section 6, which forbids the
imperative. `HowTo` binds to Section 5, with a 15-word sentence cap. Whichever you choose, you
break something. Relatedly, Section 6's scope names only two types, so **a descriptive sentence
inside a `HowTo` has no stated word limit at all.**

**ACE 3.7 cannot express a counterfactual.** `can`, `must`, `will` — none of them states what a
rejected option *would* have cost. That is the substance of a decision record's "considered
options". Our corpus ended with 346 uses of `would` that no permitted modal could replace without
turning a refused alternative into a claim about the shipped system. This is a correctness issue,
not a style one.

**ACE 15.3 breaks ACE 9.2.** ACE 9.2 restricts "above" to physical position and requires "more
than" for a limit. ACE 15.3 reads "When a document goes above a limit". Meanwhile `about.md`
claims the kit obeys its own rules. Small, but it is the first thing a careful reader checks, and
agents copy the violating phrasing.

**The dictionary has no Z.** `core-w-y.md` is the last part. `ZERO` is therefore unaddable by the
documented procedure, while `NEGATIVE`'s own definition reads "less than zero". We extended the
file to W–Z. Similarly `COLOR` was absent, which blocks any product with a theme; we added it.

## Where the standard met a real repository

ACE-100 assumes documentation is free-standing. In a live repo it is load-bearing infrastructure,
and several rules collide with things that cannot move.

**ACE 13.2 (front matter) breaks tooling that reads line 1.** This repo has a test asserting that
every ADR's first line is its `# ` title, and that the title matches its index row verbatim. Add
front matter and every conforming ADR reads as headless. We fixed the test — but an adopter
without one would simply have shipped a silent break. **The kit should warn that front matter is a
breaking change for any tool that parses document heads**, and ship a note on migrating them.

**ACE 11.3 (the index is `README.md`) collides with established index names.** This repo routed
through `docs/adr/INDEX.md` and `.scratch/INDEX.md`, named in a test, in the agent instructions,
and in ~29 documents. Conforming meant renaming both and repairing every reference. That is
survivable once, and it is exactly the kind of churn that makes a team decline the standard.
Consider permitting a declared index name per directory.

**ACE 14.1 and 11.3 against version control.** Our tickets live at
`.scratch/<feature>/issues/<NN>-<slug>.md`, and **457 commits carry a `Ticket: <path>` trailer**.
`git log --grep` follows no rename. Moving a ticket to `<slug>/README.md` to satisfy ACE 11.3
orphans it from its own history. Four separate agents made that move before we caught it and
reverted 27 files. **A rule that renames files needs an explicit carve-out for paths that history,
tooling, or external systems reference.**

**Quoted data cannot obey the language rules, and the standard does not say what to do.**
Tracker fields (`**Status:** delivered — <sha>`), test names, error strings, catalog values in six
languages, and quotations from superseded documents all contain semicolons, `-ing` forms,
contractions, British spellings, and unapproved words. ACE 1.5 exempts backticked text, but a
status line is not an identifier. We ruled that tracker data is verbatim; the standard should
address structured data embedded in prose directly.

## What worked, and worked well

This is not a negative report. The architecture half of ACE-100 is excellent, and we would keep it.

- **Front matter with a declared type** made ~1,800 documents machine-navigable. Knowing whether a
  file is an index, a description, or a procedure before reading it is worth real money to an agent.
- **One index per directory (ACE 11.4's link-plus-purpose form)** is the single best rule in the
  kit. Routing from a root index to any document became reliable for the first time.
- **The size limits, as a forcing function, found genuine rot.** A 917-line build-failures file
  became 40 symptom-addressable documents; a reader with one error message now lands on the fix.
  Two source contradictions surfaced only because someone had to read every line to divide it —
  one about a database readiness gate, one where a ticket claimed "four cases" and listed five.
- **The safety rules (Section 7) and active-voice/simple-tense rules produced better prose.**
  Genuinely. The `WARNING`/`CAUTION` discipline improved the procedures noticeably.
- **The kit obeys its own architecture rules**, which meant we could validate our conformance
  checker against the kit itself — a passing run on `docs/standard/*` was strong evidence the
  checker matched the standard's intent. That was more useful than the checklist.

## Suggestions for Issue 2

1. **Split the vocabulary.** Closed function words; open, declared domain words. This is the
   change that decides whether ACE-100 is adoptable.
2. **Ship a conformance checker.** We wrote one (~140 lines of bash) covering front matter and its
   mandatory properties, H1-versus-`name`, both size limits, spelling, link resolution, and the
   index rule. Without it, 30 agents would have produced 30 dialects. The kit should not leave
   this to each adopter — and building it forces the ambiguities (see ACE 8.5) into the open.
   Crucially, ship it knowing what it *cannot* check: ours stays deliberately silent on vocabulary
   so a green run never implies conformance it did not verify.
3. **Make ACE 15.1 deterministic, or drop its (M).** Pick one counting rule. If tables stay
   exempt, say why, and expect them to be used as an escape.
4. **State the division shape canonically.** When `topic.md` exceeds the limit, does it become
   `topic/README.md`, or stay as the index of `topic/`? We did not specify it, and got three
   different shapes across 30 agents, then had to normalize. The standard should just decide.
5. **Add a counterfactual modality**, or exempt "considered options" sections from ACE 3.7.
6. **Add a migration chapter**: front matter breaks head-parsers; renames break history and
   tooling; embedded structured data is not prose. These are the things that actually hurt.
7. **Reconsider what the size limits optimize.** The stated goal is protecting an agent's context
   window. We went from 227 files to ~1,800. Total bytes went *up* — every document now carries six
   lines of front matter, and an index hop costs a read. For a human, navigation improved. For an
   agent answering one question, we are genuinely unsure the trade is positive, and we would want
   the standard to argue it rather than assert it.

## The honest summary

We would adopt the architecture again tomorrow. Types, front matter, indexes, and a size discipline
made a large documentation set navigable, and the forcing function found real defects.

We would not adopt the closed vocabulary again in this form. It is the rule that consumed the most
effort, produced the most strained prose, and is the one rule we still do not obey — after adding
words, declaring 188 technical terms, and reviewing every rejection. Every one of ~30 independent
agents reached that conclusion separately, which is about as strong a signal as this kind of
exercise can produce.

The full record of what this repository does not obey, and why, is in
`.scratch/ace-100/deviations.md`.
