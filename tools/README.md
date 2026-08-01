---
"@type": CollectionPage
name: Tools
description: This index routes readers to the two conformance checkers of the kit.
isPartOf: README.md
---

# Tools

Two checkers settle the mechanical rules (ACE 17.2). Run the two before each review. A clean run is necessary and not sufficient (ACE 17.3): vocabulary choice, voice, meaning, and topic division need a reader.

## The checkers

- [check.sh](check.sh). The canonical checker. Zero dependencies. Front matter, the H1, the size limit, spelling, links, backticked paths, and indexes. Adapted from the checker of the first field migration.
- [lint.py](lint.py). The extended linter. Sentence and paragraph limits with the canonical count, modality, contractions, the progressive form, replacements-table words, types, and exemptions.
