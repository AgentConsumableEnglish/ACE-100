---
"@type": CollectionPage
name: Tools
description: This index routes readers to the checkers, the measurement tool, and the reader tool of the kit.
isPartOf: README.md
---

# Tools

Two checkers settle the mechanical rules (ACE 17.2). Run the two before each review. A clean run is necessary and not sufficient (ACE 17.3): vocabulary choice, voice, meaning, and topic division need a reader.

## The checkers

- [check.sh](check.sh). The canonical checker. Zero dependencies. Front matter, the H1, the size limit, spelling, links, backticked paths, and indexes. It reads markdown alone. Adapted from the checker of the first field migration.
- [lint.py](lint.py). The extended linter. Sentence and paragraph limits with the canonical count, modality, contractions, the progressive form, replacements-table words, types, and exemptions. It also reads the comments of source files (ACE 10.1).

## The comment sweep

`lint.py` reads a source file with one of these extensions:

| Family | Comment | Extensions |
|---|---|---|
| C | `//` and `/* */` | `.ts` `.tsx` `.js` `.jsx` `.mjs` `.cjs` `.go` `.rs` `.java` `.c` `.h` `.cpp` |
| Hash | `#` | `.py` `.sh` `.bash` `.rb` `.yaml` `.yml` `.toml` |
| SQL | `--` and `/* */` | `.sql` |
| Block | `/* */` | `.css` `.scss` |

An extension outside the table is not swept. It is not compliant either, and ACE 17.8 states the hole.

Put build output and vendored code in `.ace-ignore` before the first sweep. Until Issue 4 the checkers read markdown alone, and a `dist` tree had no reason for a pattern. Comment coverage needs `python3`, because `check.sh` reads markdown alone. A fuller extractor, with a parser for each language, is intended for a later issue.

## The measurement

- [measure.py](measure.py). The corpus measurement. The bytes of each document, the corpus total, and the front-matter share. Bytes are exact, and a token count is an estimate. A run never fails: the tool is a diagnostic, not a checker.
- [issue-3.txt](measurements/issue-3.txt). The snapshot of Issue 3.
- [issue-4.txt](measurements/issue-4.txt). The committed snapshot of this issue. The quantitative claims of the standard stand on it.

## The reader

- [describe.sh](describe.sh). The corpus listing. The path and the `description` of each governed document, one row for each. Zero dependencies. A reader probes with it before a load (ACE 19.1). It is not a checker, and it never fails on content.
