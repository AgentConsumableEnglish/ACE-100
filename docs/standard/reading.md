---
"@type": TechArticle
genre: rules
name: Section 19 — Reading
description: Section 19 gives the rules for a reader of a governed corpus, and the probes that the corpus supports.
isPartOf: docs/standard/README.md
---

# Section 19 — Reading

Sections 1 to 18 tell a writer what to produce. This section tells a reader how to use it.

Two rules already pay for a reader. ACE 13.2 puts a description on every document. ACE 11.3 puts an index in every directory. Each rule serves a reader that no rule described until now.

## Rules

**ACE 19.1** — Read the description of a document before you read the document.

**ACE 19.2** — Read the index of a directory to find a document in it. The index names each document and gives one line for each (ACE 11.3).

**ACE 19.3** — Read a cited document when your task needs the fact that the citation names. ACE 10.7 keeps a file-local fact in its file. A citation points at a fact that more than one file holds.

**ACE 19.4** — Do not copy the description of a document to the place that cites the document. ACE 14.7 holds: one fact lives in one document.

**ACE 19.5** — Read the whole document before you change it. A description is a pointer, and never a substitute.

## The probes

[describe.sh](../../tools/README.md) gives the path and the description of each governed document:

```bash
tools/describe.sh docs           # every document under docs
tools/describe.sh docs migrate   # the rows that match "migrate"
```

Two commands do the same work for one document, without the tool:

```bash
awk '/^---$/{n++} n<2' <file>            # the front matter alone
awk 'f; /^---$/{n++} n==2{f=1}' <file>   # the body, without the front matter
```

## What this section does not claim

This section makes no claim about tokens or turns. No committed measurement settles what a read protocol costs. [About ACE-100](about.md) forbids a quantitative claim without a measurement.

The rules above stand on simpler ground. The corpus already carries a description and an index. A reader that skips them pays the cost and takes nothing.
