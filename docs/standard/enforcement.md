---
"@type": TechArticle
genre: rules
name: Section 17 — Enforcement
description: Section 17 gives the rule identifiers, the checker coverage table, the exemptions, and the review process.
isPartOf: docs/standard/README.md
---

# Section 17 — Enforcement

**ACE 17.1** — Each rule has a stable identifier, in the format `ACE <section>.<rule>`. Recommendations use `ACE R<number>`. [changes.md](changes.md) records identifier changes between issues.

**ACE 17.2** — The mark `(M)` means that a machine can settle the rule. The mark is a claim about the rule, not about the kit. The table below gives the checker that settles each such rule. The kit ships the two checkers in [tools](../../tools/README.md):

- `check.sh` is canonical. It has zero dependencies. It reads markdown alone.
- `lint.py` extends it with the pattern rules, and it reads the comments of source files (ACE 10.1).
- A rule with "none" in its checker column is a known hole. The kit does not settle it. Plan a reader or a local check there.
- A row with "part" settles the named part alone. The rest of that rule needs a reader.

| Rule | Checker | Coverage |
|---|---|---|
| ACE 1.1 | none | The function layer needs a part-of-speech read |
| ACE 1.3 | `lint.py` (part) | The replacements rows and the deletions. A row with a context note needs a reader |
| ACE 1.5 | none | What is an identifier needs a reader |
| ACE 1.12 | `check.sh` | The frequent British spellings, in prose |
| ACE 3.3 | `lint.py` (part) | The progressive form ("is running"). The perfect tenses need a reader |
| ACE 3.7 | `lint.py` | The banned modality words. Each "would" outside a decision record gets a review note |
| ACE 4.2 | `lint.py` (part) | Contractions. The dropped subjects and articles need a reader |
| ACE 5.1 | `lint.py` | The 15-word limit, with the ACE 8.5 count |
| ACE 6.1 | `lint.py` | The 20-word limit, on logical sentences (ACE 8.8) |
| ACE 6.6 | `lint.py` | The five-sentence paragraph limit |
| ACE 7.1 | none | The level-word format is not checked |
| ACE 8.1 | `lint.py` | Semicolons in prose |
| ACE 8.4 | `lint.py` | Latin abbreviations |
| ACE 9.4 | none | A repeated fact needs a reader |
| ACE 10.4 | `lint.py` (part) | The label exempts a source file. A missing label is not checked |
| ACE 10.8 | `lint.py` | The terminal punctuation that divides a sentence from a fragment |
| ACE 10.9 | `lint.py` | The `ace-exempt` comment, and the ledger must exist |
| ACE 11.3 | `check.sh` | One `README.md` index in each governed directory |
| ACE 12.1 | `lint.py` | The `@type` value is one of the five |
| ACE 12.2 | none | A checker cannot tell that a document is a record. ACE 15.2 step 5 keeps the genre |
| ACE 12.5 | `lint.py` | The `genre` value is a declared genre |
| ACE 13.1 | `check.sh` | The front-matter block opens and closes |
| ACE 13.2 | the two | The mandatory properties, the `isPartOf` resolution, the description length |
| ACE 13.6 | `check.sh` | The H1 equals `name` |
| ACE 13.7 | the two | An exempt rule is not applied to its document |
| ACE 14.1 | `lint.py` | Kebab-case filenames |
| ACE 14.2 | `check.sh` | Through the index check (ACE 11.3) |
| ACE 14.3 | `lint.py` | Heading depth H1 to H3 |
| ACE 14.5 | `check.sh` | Each link resolves, and points at a file |
| ACE 14.9 | the two | Each backticked repository path resolves, in a document and in a comment |
| ACE 15.1 | the two | The 120-line body count |
| ACE 16.1 | none | The checkers do not read git |
| ACE 17.7 | the two | The `exempt` property, and the ledger must exist |
| ACE 19.1 | none | A checker cannot see how an agent read a document |
| ACE 19.5 | none | The same hole |

**ACE 17.8** — Comment coverage needs `python3`. `check.sh` reads markdown alone, so a repository without `python3` gets no comment check at all. The rules still hold, and the sweep does not report them. [The tools index](../../tools/README.md) names the file extensions that the sweep reads. An extension that is absent from that list is unchecked, and it is not compliant.

**ACE 17.3** — Each checker states what it does not check. A clean run is necessary and not sufficient. Vocabulary choice, voice, meaning, and topic division need a reader.

**ACE 17.4** — In a review, cite the rule identifier with each error. ("This sentence breaks ACE 5.1.")

**ACE 17.5** — The dictionary owners review each change to `docs/dictionary/`. `CODEOWNERS` routes these changes. The owners have one check: no existing word covers the same concept.

**ACE 17.6** — A reviewer checks a document against [the checklist](checklist.md) before approval.

**ACE 17.7 (M)** — A deviation is legal only when it is declared. The document carries `exempt` (ACE 13.7), and [deviations.md](deviations.md) carries the row. An undeclared deviation is an error. A declared one is a record.
