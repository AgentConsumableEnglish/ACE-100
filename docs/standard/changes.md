---
"@type": TechArticle
name: Issue history
description: This document records the changes between the issues of ACE-100.
isPartOf: docs/standard/README.md
---

# Issue history

## Issue 3 — draft

This issue is a draft. More changes can join it before the release.

A second field report from the same monorepo drove this issue. The corpus passed the Issue 2 checkers on day one. The report still found 99 gone parents, 159 dropped genres, and 101 stale backticked paths. Every rotted rule was `(M)` with no checker, and every checked rule was at zero findings. The architecture rules got the enforcement that the language rules got in Issue 2.

- ACE 17.2: the `(M)` mark became a coverage table. Each machine-settleable rule names the checker that settles it, and a "none" row is a visible hole.
- ACE 15.2: a new step 5. A part inherits the `@type`, the `genre`, and the `exempt` of its source, and its `isPartOf` is the new index.
- ACE 14.9: a backticked repository path must resolve, and `check.sh` settles it. Field data: four conforming divisions left 101 stale paths, in prose, source comments, and a SQL migration.
- ACE 8.8: every count applies to the logical sentence. A line wrap changes no count.
- ACE 3.4: the rule is about grammar, not about letters. A deverbal noun is an open content word, and the allowlist is retired. Field data: the list grew from 22 rows to 63 in one pass.
- Section 6: a note warns that a sentence division can push a paragraph past the ACE 6.6 limit.
- The checkers: `lint.py` settles ACE 6.6, counts logical sentences, treats a blockquote as quoted text, and reports the progressive form (ACE 3.3).

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
