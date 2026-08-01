---
"@type": CollectionPage
name: Tools
description: This index routes readers to the conformance checkers and the measurement tool of the kit.
isPartOf: README.md
---

# Tools

Two checkers settle the mechanical rules (ACE 17.2). Run the two before each review. A clean run is necessary and not sufficient (ACE 17.3): vocabulary choice, voice, meaning, and topic division need a reader.

## The checkers

- [check.sh](check.sh). The canonical checker. Zero dependencies. Front matter, the H1, the size limit, spelling, links, backticked paths, and indexes. Adapted from the checker of the first field migration.
- [lint.py](lint.py). The extended linter. Sentence and paragraph limits with the canonical count, modality, contractions, the progressive form, replacements-table words, types, and exemptions.

## The measurement

- [measure.py](measure.py). The corpus measurement. The bytes of each document, the corpus total, and the front-matter share. Bytes are exact, and a token count is an estimate. A run never fails: the tool is a diagnostic, not a checker.
- [issue-3.txt](measurements/issue-3.txt). The committed snapshot of this draft. The quantitative claims of the standard stand on it.
