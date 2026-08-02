---
"@type": TechArticle
genre: rules
name: Section 18 — Migration
description: Section 18 gives the rules for a rewrite of an existing repository into ACE-100.
isPartOf: docs/standard/README.md
---

# Section 18 — Migration

A live repository is not a blank page. Its documents are infrastructure: tests read them, tools parse them, and history points at them. These rules come from a full migration of 227 documents.

**ACE 18.1** — Run a checker from the first file. Independent writers without a shared checker produce dialects. Give each writer [tools/check.sh](../../tools/README.md) and the [agent brief](agent-brief.md).

**ACE 18.2** — Before you add front matter, find every tool that reads the first line of a document. Examples: a test that compares titles, and a script that reads line 1. Repair each tool in the same change, or the break is silent.

**ACE 18.3** — Before you rename or move a document, search for its path in history trailers, tests, and external links. If the path is load-bearing, keep it and declare it exempt (ACE 14.8).

**ACE 18.4** — Keep structured data verbatim (ACE 10.6). A status line, a tracker field, and an error string are values, not prose. Put the front matter above them, and do not translate them.

**ACE 18.5** — Rewrite meaning-first (ACE 9.1). If a rule and a document's claim conflict, keep the claim, and report the conflict. A migration must not change what a repository asserts.

**ACE 18.6** — Divide with the canonical shape (ACE 15.2), and only after the whole batch is known. Repair cross-batch links in one later pass, when every division is final.

**ACE 18.7** — Record every deviation in [deviations.md](deviations.md) as you find it, not at the end.

**ACE 18.8** — Migrate the comments in two phases. Phase one is layer L1: words, verbs, and punctuation. Phase two is layer L2: the sentence and paragraph limits. Phase one is cheap, and each finding has a one-word repair.

**ACE 18.9** — The end state that this standard recommends is a clean sweep. How a repository reaches it is a decision of that repository. A baseline of existing findings and a check of changed files alone are two other paths. Each one weakens ACE 17.3: after it, a clean run means the findings that the repository already had.
