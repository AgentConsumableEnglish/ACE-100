---
"@type": TechArticle
name: Issue history
description: This document records the changes between the issues of ACE-100.
isPartOf: docs/standard/README.md
---

# Issue history

## Issue 4 — 2026-08-03

The standard governed code comments from Issue 1, and no checker ever read one. `check.sh` and `lint.py` swept markdown alone, so the ACE 17.2 table overstated its reach. In the field repository, comment prose runs to 324,000 words against 500,000 words of markdown. Two of every five words of prose in that repository had never met a checker.

- ACE 10.7: a comment states what is true of its own file. A fact true across files lives in a document, and the comment cites it. ACE 9.4 and ACE 14.7 give the same rule for documents.
- ACE 10.8: a comment that ends with terminal punctuation is a sentence, and layer L2 reaches it. Other comment text is a fragment. The Issue 3 note became a rule that a machine settles.
- ACE 10.9: a source file has no front matter, so it declares a deviation in an `ace-exempt` comment. The declaration covers the file, and ACE 17.7 still demands the ledger row.
- ACE 10.4 and ACE 10.6: the generated-file label has a source form, and a comment directive that a tool reads is verbatim.
- ACE 14.9: the rule reaches a comment. A division moves the path and leaves the comment behind.
- Section 19: a new section, and the first read-side rules of the standard. ACE 13.2 puts a description on every document and ACE 11.3 puts an index in every directory, and until now no rule said what either was for.
- Section 18: ACE 18.8 phases a comment migration, L1 before L2. ACE 18.9 recommends a clean sweep, and leaves the path to the adopting repository.
- ACE 17.8: comment coverage needs `python3`, and an extension outside the swept list is unchecked rather than compliant.
- The checkers: `lint.py` extracts comments from four syntax families, and it tracks string literals. Layer L1 reaches every comment, and layer L2 reaches its sentences. `check.sh` states that it reads markdown alone.
- The tools: [describe.sh](../../tools/README.md) is the first reader tool of the kit. It prints the path and the description of each governed document. `measure.py` reports the comment corpus beside the documents, and `tools/measurements/issue-4.txt` is the snapshot.
- The briefs: [the reader brief](reader-brief.md) joins the agent brief. It serves an agent that consumes a corpus, and not one that writes it.

The kit failed the new checker on the day it was written: four semicolons and ten long sentences in `check.sh`, and eleven more in the adopt command. The `.ace-ignore` file stopped excluding the whole development tree, because one file in it ships. Published means governed.

Three placement questions stayed open, and no rule closed them. Does collocated prose beat a cited document? Does the ACE 6.1 limit transfer to comment prose? Does an identifier citation need to resolve?

Each question is recorded as a claim, with the measurement that settles it. None of them is answered here.

## Issue 3 — 2026-08-01

A second field report from the same monorepo drove this issue. The corpus passed the Issue 2 checkers on day one. The report still found 99 gone parents, 159 dropped genres, and 101 stale backticked paths. Every rotted rule was `(M)` with no checker, and every checked rule was at zero findings. The architecture rules got the enforcement that the language rules got in Issue 2.

- ACE 17.2: the `(M)` mark became a coverage table. Each machine-settleable rule names the checker that settles it, and a "none" row is a visible hole.
- ACE 15.2: a new step 5. A part inherits the `@type`, the `genre`, and the `exempt` of its source, and its `isPartOf` is the new index.
- ACE 14.9: a backticked repository path must resolve, and `check.sh` settles it. Field data: four conforming divisions left 101 stale paths, in prose, source comments, and a SQL migration.
- ACE 8.8: every count applies to the logical sentence. A line wrap changes no count.
- ACE 3.4: the rule is about grammar, not about letters. A deverbal noun is an open content word, and the allowlist is retired. Field data: the list grew from 22 rows to 63 in one pass.
- Section 6: a note warns that a sentence division can push a paragraph past the ACE 6.6 limit.
- The checkers: `lint.py` settles ACE 6.6, counts logical sentences, treats a blockquote as quoted text, and reports the progressive form (ACE 3.3). Without git, `check.sh` reads the current directory as the root.

A review of [caveman](https://github.com/JuliusBrussee/caveman), a compression project for agent replies, also joined this issue. Documentation output becomes input for future sessions. Thus a dense document saves context in every later read. The review took the practices that keep full grammar, and it refused the fragment style. The changes below have this source, not a field report.

- ACE 9.4: state each fact one time in a document. ACE 14.7 gives the rule between documents. A repeated fact needs a reader.
- ACE 15.4: when many examples show one pattern, keep one example.
- ACE 16.2: the diff shows what a change does, and the commit body tells why.
- ACE 17.2: rows for ACE 1.3 and ACE 9.4 joined the coverage table.
- Dictionary: a deletions table joined [replacements.md](../dictionary/replacements.md), with eight words that add no meaning. The ACE 1.3 check settles the deletions.
- Tools: `tools/measure.py` reports the bytes of each document, the corpus total, and the front-matter share. Bytes are exact, and a token count is an estimate. The snapshot of this issue is `tools/measurements/issue-3.txt`.
- About: a new self-compliance rule. The standard makes no quantitative claim without a committed measurement.
- Front matter: the audit kept every property. The block lets an agent decide from four lines, without the body. The known duplication is the `name` and H1 pair (ACE 13.6). A trim waits for field evidence from the monorepo.

This issue also gained a release pipeline. This work changes the kit, not a rule.

- Release: each issue is a GitHub release. The assets are the kit archive, the skill archive, and the adopt command.
- Adoption: the adopt command adopts a repository, or upgrades it to a newer issue.
- A manifest separates the files of the standard from the three files that an adopter extends.
- Upgrades overwrite the files of the standard, keep the files of the adopter, and remove dropped files.
- Skill: the `ace-migrate` skill guides an agent rewrite of an existing repository. The `--migrate` flag installs it into the shared skills directory.

## Issue 2 — 2026-07-31

A full migration of a real monorepo (227 documents, ~1,800 after division, ~30 independent writers) drove this issue. The migration report is the source of each change.

- ACE 1.1: the closed vocabulary became two layers. The function core stays closed. Content words are open, with style rules. Field data: a 605-word core left more than 500 unapproved word forms in each product area.
- ACE 3.7: "would" is approved for counterfactual conditions only. Field data: 211 uses that no permitted modal replaces without a change of meaning.
- ACE 8.7: the second count of parenthetical text is repealed. One counting rule (ACE 8.8).
- ACE 12.5: the `rules` genre gives rule documents a defined binding.
- ACE 13.7, 17.7: declared exemptions and the deviations ledger.
- ACE 14.8: load-bearing paths do not move. Field data: 457 commit trailers, 27 reverted files.
- ACE 15.1: one size limit, 120 body lines, everything counts. The 250-word cap is retired, and the old ACE 15.2 joined 15.1. The new 15.2 is the canonical division shape.
- ACE 15.5: the priority order between 15.5, 15.1, and 14.7 is stated.
- ACE 16.1: structured commit prefixes and trailers are identifiers.
- ACE 10.6, 18.1 to 18.7: verbatim data and the migration section.
- ACE 6.1: the descriptive sentence limit applies in every document type.
- The kit ships two checkers, the agent brief, and this history.
- Dictionary: `ZERO`, `COLOR`, `WITHOUT`, and the recurring function words joined the core. The Issue 1 content shards are retired.

## Issue 1 — 2026-07-31

The first issue: the writing rules, the architecture, the closed vocabulary, the seed dictionary, the templates, and the example.
