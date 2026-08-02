---
"@type": TechArticle
genre: rules
name: Coverage and layers
description: Section 10 tells which prose the standard governs and which rule layers apply to it.
isPartOf: docs/standard/README.md
---

# Coverage and layers

The standard governs all prose that a person or an agent writes in the repository. This includes markdown documents, code comments, docstrings, commit messages, and PR text. The rules apply in three layers.

## The layers

| Layer | Rules | Applies to |
|---|---|---|
| L1 | Words, verbs, punctuation (Sections 1 to 3, 8, 9) | All governed prose |
| L2 | Sentences, paragraphs, safety (Sections 4 to 7) | Documents, docstrings, comment sentences, commit bodies, PR text |
| L3 | Architecture (Sections 11 to 15) | Markdown documents only |

## Rules

**ACE 10.1** — Apply layer L1 to all governed prose.

**ACE 10.2** — Apply layer L2 to all prose that has full sentences.

**ACE 10.3** — Apply layer L3 to markdown documents only.

**ACE 10.4 (M)** — A generated file is exempt. Put a label in the file that tells:

- That a tool generated the file.
- The name of the tool or the source.

In a source file, the label is a comment in the first lines. The comment checker reads the label, and it leaves the file alone.

**ACE 10.5** — Write governed prose in English only.

**ACE 10.6** — Structured data embedded in prose is verbatim. Examples: tracker fields, status lines, error strings, quoted legacy text, and a comment directive that a tool reads. Do not change it, and do not apply the language rules to it. Keep it in the exact form that its tool reads.

**ACE 10.7** — A comment states what is true of its own file. A fact that is true across files lives in a document, and the comment cites that document. ACE 9.4 and ACE 14.7 give the same rule for documents.

**ACE 10.8 (M)** — Comment prose that ends with a period is a sentence. A question mark and an exclamation mark end a sentence too. Layer L2 applies to a sentence. Other comment text is a fragment, and layer L1 alone applies.

**ACE 10.9 (M)** — A source file has no front matter, so it declares a deviation in a comment:

```
// ace-exempt: ACE 6.1 — the reason for the deviation
```

The declaration covers the whole file. The obligations of ACE 13.7 and ACE 17.7 hold: name each rule, give the reason, and add the row to [the deviations ledger](deviations.md).
