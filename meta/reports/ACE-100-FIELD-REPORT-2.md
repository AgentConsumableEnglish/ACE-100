# ACE-100 Issue 2 — a second field report

Feedback for the authors of the ACE-100 kit, from the same repository, one issue later.

**This document is deliberately not written in ACE-100**, for the same reason as
[the first report](ACE-100-MIGRATION.md), and it is excluded from the conformance sweep. Issue 2
removed one of the two reasons: ACE 3.7 now permits the counterfactual, so the sentences below about
what a checker *would* have caught are expressible. The other reason stands, and the last section
says why.

## What this pass was

Not a migration. The corpus was already conforming: `tools/check.sh` passed on all 1,819 governed
documents on the day this started, and [the deviations ledger](docs/standard/deviations.md) recorded
2,383 open findings from `lint.py` — the linter Issue 2 ships and Issue 1 did not have. The task was
to close them.

| | |
|---|---|
| Governed documents | 1,819 |
| `check.sh` before and after | clean |
| `lint.py` findings before | 2,383 |
| `lint.py` findings after | 1,429 |
| Findings in `docs/` and `apps/` before | 650 |
| Findings in `docs/` and `apps/` after | 4 |
| Documents edited | 342 markdown, 37 source files |
| Rewritten by | one agent, one session |

The 1,425 findings that remain are all under `.scratch/`, which holds the session records of past
waves; those are kept as written. The product documentation is clean. The four findings left in
`docs/` are `lint.py` asking a reader to confirm a `would`, and all four are genuine counterfactuals.

## The headline: `(M)` does not mean checked, and every unchecked `(M)` rule had rotted

ACE 17.2 says the mark `(M)` means that a machine can settle the rule. In practice it is read as
"the shipped checkers handle this". They do not. ACE 17.3 asks each checker to state what it does
not check, and both do — but in prose, by rule *family*, not by identifier. So the gap between a
rule being settleable and a rule being settled is invisible from either end.

Three mandatory rules were marked `(M)` and settled by neither checker. All three had silently
broken:

| Rule | What it mandates | What we found |
|---|---|---|
| **ACE 13.2 (M)** | `isPartOf` is "the path of the parent index, from the repository root" | **99 documents named a parent that does not exist** — 5.5% of the corpus |
| **ACE 12.2 (M)** | A decision record carries `genre: decision-record` | **159 of 189 ADR parts carried no genre.** All 43 top-level records had it |
| **ACE 6.6 (M)** | Five sentences maximum in each paragraph | 11 paragraphs over the limit, and no way to see them |

Every `(M)` rule that a shipped checker actually settles was at zero across 1,819 documents: front
matter presence, the H1, the size limit, spelling, link resolution, the index rule, contractions,
semicolons, filenames. Not approximately zero. Zero.

**The correlation is total, and it is the most useful thing this pass learned.** A rule that is
checked holds. A rule that is merely marked checkable rots at whatever rate the corpus changes. The
distance between "a machine could settle this" and "a machine does settle this" is the whole of
conformance in practice.

**Suggestion.** Make ACE 17.2 a table rather than a mark. For each rule: is it machine-settleable,
and which shipped checker settles it? A rule that is `(M)` with an empty checker column is a known
hole an adopter can see and plan around. As it stands, `(M)` reads as a promise the kit does not
keep, and an adopter has no way to learn which half they got.

## Division breaks pointers, and ACE 15.2 almost says so

ACE 15.2 gives the canonical division shape, and its step 4 reads: *"Repair the links to the old
path, or declare the old path exempt (ACE 14.8)."*

That sentence is correct and incomplete. Turning `topic.md` into `topic/README.md` plus parts breaks
three kinds of pointer. Step 4 names one of them.

### 1. The `isPartOf` of every new part

The parts are cut from a document whose parent was somewhere else. Their parent is now
`topic/README.md`. Nothing in ACE 15.2 says to rewrite it, and nothing checks it, so the parts keep
a value that points at the file the division just deleted.

We found this four times over, always the same accident:

| Broken parent | Documents |
|---|---|
| `docs/build-gotchas.md` | 40 |
| `docs/agents/wave-agent-brief.md` | 15 |
| `docs/agents/wave-orchestrator-brief.md` | 15 |
| `.scratch/spaces-documents-ui/spec.md` | 15 |
| three more of the same shape | 14 |

**The rule that mandates the property and the rule that breaks it are both in the standard, and
neither one mentions the other.**

### 2. The genre of every new part

ACE 12.2 (M) makes `genre: decision-record` mandatory for a decision record. ACE 15.2 divides a
decision record into parts. Nothing says the parts are still decision records, so nobody wrote the
genre on them: 43 of 43 top-level records carried it, 0 of 189 parts did.

This one is not cosmetic, because the genre is load-bearing for a *language* rule. ACE 3.7 permits
`would` for a counterfactual, and the reference linter reads `genre: decision-record` to decide
whether a `would` needs a reader. With the genre gone, **58 legal counterfactuals inside decision
records were reported as errors** — in the "considered options" and "rejected options" documents that
Issue 1's suggestion 5 was written to protect. Issue 2 added the counterfactual modality, and then
division quietly took it back.

**Suggestion.** One clause on ACE 15.2: *a part inherits the `@type`, `genre` and `exempt` of the
document it was divided from, and its `isPartOf` is the new index.* One sentence closes 99 broken
parents and 159 missing genres.

### 3. Backticked paths, which ACE 1.5 exempts from everything

This is the finding we would most like acted on, because it is a rule interaction rather than an
omission, and because it reaches outside the documentation.

ACE 14.5 requires links to resolve and the checker enforces it — which is why link rot was at zero.
ACE 1.5 exempts backticked text from the word rules, because it is an identifier. In a real
repository a large share of document references are written as backticked paths
(`` `docs/build-gotchas.md` ``) rather than as markdown links: in prose *about* a file, in code
comments, in commit-adjacent text where a relative link has no meaningful target.

**A backticked path is an identifier and a pointer at the same time. ACE 1.5 exempts it as the
former, and every adopter reads that as exemption from the latter.** A checker that validates every
link therefore validates none of these.

Four divisions left **101 stale backticked paths** behind. We repaired 66 of them:

| Where | Occurrences |
|---|---|
| Prose in `docs/` | 15 |
| Source: 34 TypeScript and TSX files, 2 shell scripts, 1 SQL migration | 51 |
| `.scratch/` session records, left as written | 35 |

Every one of them was correct when written. Every one was broken by a division that ACE 15.1
required and ACE 15.2 shaped. And none was visible to any check in either direction: the author
doing the division had no way to find the references, and a later reader had no way to learn the
target was gone. **A stale pointer in a SQL migration comment is a long way from a documentation
problem, and the size rule put it there.**

**Suggestion.** Add a rule with a checker: *a backticked span shaped like a repository path must
resolve.* Ours is a dozen lines. If that is too broad a claim over backtick contents, the narrow
version works as well: *a reference to another governed document is a link (ACE 14.5), never a
backticked path* — which makes the existing checker sufficient and costs the standard nothing.

## Two rules that fight, and the fight is invisible

### Repairing ACE 6.1 breaks ACE 6.6

The obvious repair for a descriptive sentence over 20 words is to split it in two. Do that at scale
and the paragraph gains a sentence. ACE 6.6 (M) caps a paragraph at five.

We split roughly 400 sentences. **Paragraphs over the ACE 6.6 limit went from 11 to 25 before we
noticed**, because nothing reports it. A second pass brought it to 1.

This is not a contradiction of the kind Issue 1 catalogued — both rules can hold at once. It is
worse in one practical respect: the standard gives no warning that the repair for one rule is the
injury to the other, and no checker shows the damage. An adopter fixing sentence lengths in good
faith will make paragraph conformance worse and never find out.

**Suggestion.** Ship the ACE 6.6 count in `lint.py` — it is about ten lines — and add a line to
Section 6 saying that the repair for ACE 6.1 is often a new paragraph, not only a new sentence.

### ACE 6.1 is not invariant under line wrapping

ACE 8.8 states the goal plainly: *"Two readers or two tools that apply ACE 8.5 to 8.7 must get the
same count."* Issue 2 earned that against parenthetical text, which Issue 1 reported as
double-counted. It has not earned it against line breaks.

The reference linter counts sentences within a line. A hard-wrapped document therefore has its
sentences counted in fragments: a 30-word sentence wrapped across three lines reads as three short
ones and passes, while the same sentence on a single line fails at 30. **The same prose conforms or
does not conform depending on where an author pressed Enter.**

We hit this directly. Two of the last findings in this pass were fragments of wrapped sentences, and
the honest repair was to rewrap — which changed nothing about the prose a reader sees.

**Suggestion.** Say in ACE 8.8 that the count is over the logical sentence, independent of line
breaks, exactly as it now says for parentheses. Then join wrapped lines in the reference checker
before counting. Until that lands, the rule rewards a formatting habit, and a formatting habit is
not short sentences.

## ACE 3.4 bans a spelling, not a grammatical category

ACE 3.4 (M) forbids "-ing" forms of verbs, with two exceptions: words the dictionary approves, and
technical terms or identifiers.

The difficulty is that `-ing` is not a verb marker. It marks gerunds and participles, which the rule
means to catch, and it also marks a large open class of ordinary deverbal nouns, which the rule does
not. The kit's own allowlist concedes the point: `heading`, `warning`, `meaning`, `spelling` and
`naming` are all in it, and none is a verb form in any use.

So the escape hatch did what escape hatches do. **We grew the allowlist from 22 entries to 63 in a
single session** — `greeting`, `listing`, `encoding`, `rendering`, `wiring`, `coupling`,
`bookkeeping`, `padding`, `mapping`, `embedding`, and thirty more. Every addition is a real noun,
each was checked in context, and we refused the three that were genuinely verb forms (`reading`
where it modified a noun, `typing`, `computing`). The documented procedure worked exactly as
written. It also produced, in one pass, a 41-row table of ordinary English nouns whose only offence
is a suffix.

**This is the Issue 1 vocabulary finding one layer down.** Issue 1 predicted that
`technical-terms.md` would inflate until the closed vocabulary was open in fact and closed on paper;
that table now holds 205 rows. Issue 2 fixed the vocabulary properly, by splitting it into a closed
function core and an open content layer. ACE 3.4's allowlist is the last place in the standard where
an open class of content words is policed by a hand-maintained list.

**Suggestion.** Restate ACE 3.4 as a rule about grammar rather than about letters: *do not use a
progressive or a participial verb form.* Then note that a deverbal noun is a content word under ACE
1.1's open layer and needs no approval. That deletes the allowlist and its maintenance, and catches
the same errors — at the honest cost that no checker can settle it, so ACE 3.4 loses its `(M)` and
becomes a reader's rule. We think that trade is right, and that refusing it is what produces the
63-row table. If the allowlist stays, ship a far larger starter set: ours needed 41 additions for one
mid-size TypeScript repository, and the next repository will need a different 41.

## What Issue 2 got right

Stated plainly, because everything above is a complaint.

- **The two-layer vocabulary is the change that made ACE-100 adoptable.** Issue 1's headline was
  that ACE 1.1 does not survive contact, measured at about 1,150 unapproved word forms for a single
  product area. Across this entire pass — roughly 400 rewrites through the `docs/` and `apps/`
  trees — **we did not once need to extend the function core, declare a technical term, or ban a
  word.** `docs/dictionary/`
  has exactly one changed file, and it is the `-ing` allowlist. The closed core held and the open
  layer absorbed the rest. This was the right call and it is not close.
- **ACE 3.7's counterfactual works.** 203 of the remaining `would` findings are review notes rather
  than errors, and every one we read in `docs/` was a legal counterfactual in a considered-options or
  rejected section. That was suggestion 5, and it landed.
- **ACE 13.7 plus the ledger is the best process rule in the kit.** We met four ADR titles, frozen by
  a test, that hold `avoid`, `via`, `may` and `purging`. Under Issue 1 that would have been an
  argument. Under Issue 2 it was mechanical: `exempt` in the front matter, a row in the ledger, and
  the checker stops asking. **A standard that ships a legitimate way to disobey it gets obeyed more,
  not less.**
- **ACE 15.5's stated priority order ended a real recurring argument.** Issue 1 reported that every
  author rediscovered the 15.1-against-15.5-and-14.7 conflict alone. Writing the order down fixed
  that.
- **ACE 10.6 held.** Tracker fields, error strings and quoted legacy text stayed verbatim, with no
  fights and no exemptions needed.

## Defects in the reference checker

The kit adopted this repository's checker for Issue 2, so these are partly ours to own. Three false
positives, fixed here and worth folding upstream:

| Defect | Effect |
|---|---|
| A set of non-verb `-ing` words was named as a suffix set and used as exact membership | `substring` reported as a verb form |
| No head-word lookup for hyphenated compounds | `pre-existing` reported, though `existing` is approved |
| Blockquotes not treated as quoted text | Verbatim quotations reported, though ACE 1.5 exempts them |

The third is the instructive one. ACE 1.5 exempts quoted text, and the checker implemented that for
`"…"` spans but not for the markdown spelling of a quotation. There were only 10 blockquote lines in
the whole corpus and every one was a genuine quotation — a vendor document, a verbatim skill body, a
superseded spec — so the fix was safe. But it is a reminder that **"quoted text" in a markdown corpus
has at least three spellings, and ACE 1.5 names one.**

## What this report still cannot say in ACE-100

Issue 1 gave two reasons a document of this kind cannot conform. One is gone; one is not.

**Gone: the counterfactual.** ACE 3.7 now permits `would`, so "a checker that ran here would have
caught 99 broken parents" is expressible. Suggestion 5 worked.

**Not gone: the size limit against a sustained argument.** ACE 15.1 replaced the 250-word cap with
120 body lines, which is a real improvement — it is exact, and ACE 8.7's second count is repealed.
But this report is about 250 lines and every section leans on the one before it. Under ACE 15.1 it
becomes three documents; under ACE 15.2 it becomes a directory with an index; and then ACE 15.5 —
*"an agent must find the answer to one question in one document"* — is broken by the division ACE
15.1 required, which is precisely the failure ACE 15.5 exists to name.

ACE 15.5 does supply the escape: keep the document whole and declare it exempt. That is the correct
answer and we would take it. **But it means the standard's own honest answer for a long argument is
"do not obey the size rule", and Section 15 should say so rather than leaving each author to
rediscover it.**

## Suggestions for Issue 3

1. **Turn `(M)` into a checker column.** Per rule: machine-settleable, and which shipped checker
   settles it. Every rule we found rotted was `(M)` with no checker; every rule with a checker was at
   zero.
2. **Make ACE 15.2 carry the properties.** A part inherits `@type`, `genre` and `exempt`; its
   `isPartOf` is the new index. One sentence, two defects closed.
3. **Check that `isPartOf` resolves.** It is mandatory, it is `(M)`, and it was never verified. Ten
   lines of shell.
4. **Make a backticked repository path checkable**, or require that a document reference be a link.
   101 stale pointers, reaching into source code and a SQL migration, all produced by conforming
   divisions.
5. **Ship the ACE 6.6 paragraph count**, and warn in Section 6 that splitting a sentence is usually a
   paragraph edit.
6. **Make ACE 6.1 wrapping-invariant**, and say so in ACE 8.8 as it now says it for parentheses.
7. **Restate ACE 3.4 as a rule about verb forms rather than about the letters "ing"**, and drop the
   allowlist. If it stays, ship a starter set several times larger.

## The honest summary

**Issue 2 fixed what Issue 1 reported.** The vocabulary is adoptable, the counterfactual exists, the
size limit is computable, the division shape is canonical, and the exemption mechanism is good enough
that we used it four times without resentment. Every suggestion in the first report produced a change
we can point at in the corpus. That is a better response rate than a standards body owes anybody.

**What Issue 2 did not anticipate is that its own architecture rules are a source of entropy.** ACE
15.1 forces division, ACE 15.2 shapes it, and division breaks parent declarations, drops genres and
strands paths — silently, at a rate proportional to how seriously an adopter takes the size
discipline. The repository that obeys ACE-100 hardest accumulates the most of this rot. We found 99
broken parents, 159 missing genres and 101 dead paths in a corpus that passed the shipped checker
cleanly on the day we began.

None of that argues against the architecture. It argues that **the architecture rules need the
enforcement the language rules just got.** Issue 2's achievement was shipping a linter for Sections 1
to 9. Issue 3's should be shipping one for Sections 11 to 15, because that is where this repository —
which has now adopted the standard twice — actually loses.

We would adopt Issue 2 again tomorrow, and we would not go back to Issue 1.
