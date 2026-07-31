---
"@type": TechArticle
name: Section 17 — Enforcement
description: Section 17 gives the rule identifier format and the review process.
isPartOf: docs/standard/README.md
---

# Section 17 — Enforcement

**ACE 17.1** — Each rule has a stable identifier. The format is `ACE <section>.<rule>`, for example `ACE 5.1`. Recommendations use `ACE R<number>`.

**ACE 17.2** — The mark `(M)` after an identifier means that a machine can check the rule. A team can connect a linter or an LLM review pass to these rules. Issue 1 does not include a tool.

**ACE 17.3** — In a review, cite the rule identifier with each error. ("This sentence breaks ACE 5.1.")

**ACE 17.4** — The dictionary owners review each change to `docs/dictionary/`. `CODEOWNERS` routes these changes. The owners have one check: no approved word covers the same concept.

**ACE 17.5** — A reviewer checks a document against [the checklist](checklist.md) before approval.

## The machine-checkable set

Presence checks: front matter, mandatory properties, H1 equal to `name`, one `README.md` for each directory. Count checks: sentence words, paragraph sentences, prose words, lines, heading depth. Pattern checks: semicolons, contractions, Latin abbreviations, modality words that are not permitted, "-ing" words outside the allowlist, and words outside the dictionary.
