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
| L2 | Sentences, paragraphs, safety (Sections 4 to 7) | Documents, docstrings, commit bodies, PR text |
| L3 | Architecture (Sections 11 to 15) | Markdown documents only |

## Rules

**ACE 10.1** — Apply layer L1 to all governed prose.

**ACE 10.2** — Apply layer L2 to all prose that has full sentences.

**ACE 10.3** — Apply layer L3 to markdown documents only.

**ACE 10.4 (M)** — A generated file is exempt. Put a label in the file that tells:

- That a tool generated the file.
- The name of the tool or the source.

**ACE 10.5** — Write governed prose in English only.

**ACE 10.6** — Structured data embedded in prose is verbatim. Examples: tracker fields, status lines, error strings, quoted legacy text. Do not change it, and do not apply the language rules to it. Keep it in the exact form that its tool reads.

## Note

Short code comments are frequently not full sentences. Layer L1 applies to them. Layer L2 does not.
