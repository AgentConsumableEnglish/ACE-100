---
"@type": TechArticle
genre: rules
name: The agent brief
description: This document gives the whole ACE-100 standard in one file, for a writer.
isPartOf: docs/standard/README.md
exempt: "ACE 15.1, ACE 14.9 — one rulebook in one read, and the division line names example paths; see the deviations ledger"
---

# The agent brief

Read this once, then write. Open the full sections only when a rule needs its detail. Run `tools/check.sh` on every file you write.

## Words (Section 1)

- Function words are closed: use only the [function core](../dictionary/function-a-s.md). Content words are open.
- Do not use a word from [replacements.md](../dictionary/replacements.md). Use the simple, frequent word. Delete the words in its deletions table.
- One name for each item, in all documents. One meaning for one word.
- Backtick every identifier: commands, paths, values, names from code. Backticked text is exempt from all word rules.
- Declare real names in [technical-terms.md](../dictionary/technical-terms.md), in the same PR. Terms have three words maximum.
- American spelling in prose. Never change quoted text or code.

## Verbs and modality (Section 3)

- Simple tenses only. Active voice. No "-ing" verb forms. A deverbal noun ("the encoding") is an open content word.
- The past participle is an adjective only ("the deployed version").
- Modality: "can" = possibility or permission. "must" = obligation. "will" = future. "would" = counterfactual only.
- No phrasal verbs. ("Spin up" is not correct. Write "Start".)

## Sentences (Sections 4 to 6, 8)

- Procedural sentence: 15 words maximum. Descriptive sentence: 20, in every document type. Note: 20.
- Count method: a number, a backticked span, an identifier, quoted text, or a hyphenated group is one word. Parenthetical text counts once, in its sentence.
- Counts apply to the logical sentence. A line wrap changes no count. A sentence split can push a paragraph past five — divide the paragraph too.
- One instruction for each sentence. Condition first, then command: "When the check is green, merge."
- Keep articles and subjects. No contractions. No semicolons. No Latin abbreviations.
- Paragraphs: one topic, five sentences maximum, topic sentence first.
- State each fact one time in a document. Merge items that repeat it (ACE 9.4).
- Write "that" after report verbs: "Make sure that the test passes."

## Comments (Section 10)

- A comment is governed prose. Layer L1 reaches every comment (ACE 10.1).
- A comment that ends with a period is a sentence, and layer L2 reaches it too (ACE 10.8).
- A comment states what is true of its own file. A fact true across files lives in a document, and the comment cites it (ACE 10.7).
- A backticked path in a comment must resolve (ACE 14.9).
- A directive that a tool reads is verbatim (ACE 10.6). A generated file needs the label (ACE 10.4).
- A source file has no front matter. It declares a deviation with `// ace-exempt: ACE 6.1 — the reason`, and the ledger row still applies (ACE 10.9).

## Safety (Section 7)

- `**WARNING:**` = permanent or externally visible harm. `**CAUTION:**` = damage a team can repair.
- Level word first, then the command or condition, then the specific risk. Never in a note.
- Put safety text immediately before its step.

## Documents (Sections 11 to 15)

- Five types: `CollectionPage` (index), `TechArticle` (description), `HowTo` (procedure), `APIReference` (reference), `DefinedTermSet` (dictionary).
- Genres on `TechArticle`: `decision-record`, `rules`. A `rules` document can give reader obligations in the imperative.
- Every document starts with front matter: `"@type"`, `name`, `description` (one sentence, 20 words), `isPartOf` (parent index, from the repository root). The H1 equals `name`.
- Every governed directory has exactly one `README.md` index: links plus one-line purposes, one short lead paragraph permitted.
- Filenames are `kebab-case.md`. Headings stop at H3. Body links are relative to the file. Link to files, never directories.
- A backticked span with `/` is a path, and it must resolve too (ACE 14.9).
- Size: 120 body lines maximum, everything counts. Divide by topic: `topic.md` becomes `topic/README.md` plus parts.
- Keep code examples small. When many examples show one pattern, keep one (ACE 15.4).
- A part keeps the `@type`, the `genre`, and the `exempt` of its source. Its `isPartOf` is the new index.
- Priority when rules conflict: one-question-one-document (15.5), then the size limit, then no-repetition (14.7).
- Never move a path that history, tests, or external systems reference. Declare it `exempt` and add a ledger row.
- Structured data in prose (status lines, tracker fields, error strings) is verbatim. Front matter goes above it.

## Git prose (Section 16)

- Commit subject: imperative, 15 words, no final period. Structured prefixes and trailers are identifiers — keep them verbatim.
- Commit bodies and PR descriptions are descriptive text. Link every document the change adds or updates.
- The diff shows what a change does. The body tells why (ACE 16.2).

## When you cannot obey

- If a rule and the document's meaning conflict, keep the meaning (ACE 9.1) and report the conflict.
- A deliberate deviation needs two things: `exempt` in the front matter, and a row in [deviations.md](deviations.md).
- When a necessary dictionary change appears, [add-a-word.md](../dictionary/add-a-word.md) gives the three procedures.

## Check your work

Run the checkers before you report success:

```bash
tools/check.sh <files>   # canonical, zero dependencies, markdown alone
tools/lint.py <files>    # extended pattern checks, and source comments
```

To read a corpus rather than write one, [the reader brief](reader-brief.md) gives the read side.

A clean run is necessary, not sufficient. Vocabulary choice, voice, meaning, and division need your read.
