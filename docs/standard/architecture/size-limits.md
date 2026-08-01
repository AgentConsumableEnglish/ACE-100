---
"@type": TechArticle
genre: rules
name: Section 15 — Size limits
description: Section 15 gives the size limit, the division shape, and the priority between the size rules.
isPartOf: docs/standard/architecture/README.md
exempt: "ACE 14.9 — the division shape names example paths on purpose; see the deviations ledger"
---

# Section 15 — Size limits

**ACE 15.1 (M)** — The body of a document has a maximum of 120 lines. Everything counts: prose, tables, code blocks, and blank lines. The front matter does not count.

Issue 1 also gave a 250-word cap. Field use showed that no two tools computed it the same way, and that tables became a legal escape. Issue 2 keeps the one count that is exact.

**ACE 15.2** — This is the canonical division shape. When `topic.md` is larger than the limit:

1. Make the directory `topic/`.
2. Make one document for each subtopic inside it.
3. Change `topic.md` into `topic/README.md`, the index of the parts.
4. Repair the links to the old path, or declare the old path exempt (ACE 14.8). Repair the backticked paths too (ACE 14.9).
5. Give each part the `@type`, the `genre`, and the `exempt` of the source document. Set the `isPartOf` of each part to the new index.

A division without step 5 leaves each part with a gone parent (ACE 13.2), and drops the genre (ACE 12.2). Field data: one migration found 99 gone parents and 159 dropped genres, in a corpus that passed its checker.

**ACE 15.3** — Divide by topic, never by size alone. When a document is larger than the limit, find its topics first.

**ACE 15.4** — Keep each code example small. Show only the lines that are necessary for the topic. Link to the full file in the repository for the rest.

**ACE 15.5** — An agent must find the answer to one question in one document. This rule has priority: it outranks ACE 15.1, which outranks ACE 14.7. When a topic will not divide without this failure, keep the document whole and declare it exempt (ACE 13.7).

## What the limit optimizes

The limit exists for the reader with one question, not for small files as a goal. A small document costs an agent less context for that one question. The costs are real too: each document adds front matter, and each division adds an index hop.

A repository that divides everything pays more total bytes for better navigation. Thus the priority order above: answer-in-one-place first, size second, no-repetition third. When the three conflict, that order decides.

A sustained argument, where each section leans on the one before it, is one topic. Do not divide it. Keep the document whole, and declare the exemption (ACE 15.5, 13.7). That is the honest answer of this standard, not a defeat of it.
