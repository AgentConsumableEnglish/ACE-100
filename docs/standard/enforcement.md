---
"@type": TechArticle
genre: rules
name: Section 17 — Enforcement
description: Section 17 gives the rule identifiers, the checkers, the exemptions, and the review process.
isPartOf: docs/standard/README.md
---

# Section 17 — Enforcement

**ACE 17.1** — Each rule has a stable identifier, in the format `ACE <section>.<rule>`. Recommendations use `ACE R<number>`. [changes.md](changes.md) records identifier changes between issues.

**ACE 17.2** — The mark `(M)` means that a machine can settle the rule. The kit ships two checkers in [tools](../../tools/README.md):

- `check.sh` is canonical. It has zero dependencies and settles front matter, the H1, the size limit, spelling, links, and indexes.
- `lint.py` extends it: sentence limits, modality, contractions, "-ing" forms, and banned words.

**ACE 17.3** — Each checker states what it does not check. A clean run is necessary and not sufficient. Vocabulary choice, voice, meaning, and topic division need a reader.

**ACE 17.4** — In a review, cite the rule identifier with each error. ("This sentence breaks ACE 5.1.")

**ACE 17.5** — The dictionary owners review each change to `docs/dictionary/`. `CODEOWNERS` routes these changes. The owners have one check: no existing word covers the same concept.

**ACE 17.6** — A reviewer checks a document against [the checklist](checklist.md) before approval.

**ACE 17.7 (M)** — A deviation is legal only when it is declared. The document carries `exempt` (ACE 13.7), and [deviations.md](deviations.md) carries the row. An undeclared deviation is an error. A declared one is a record.
