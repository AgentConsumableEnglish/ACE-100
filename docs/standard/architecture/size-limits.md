---
"@type": TechArticle
name: Section 15 — Size limits
description: Section 15 gives the size limits that protect the context window of an agent.
isPartOf: docs/standard/architecture/README.md
---

# Section 15 — Size limits

**ACE 15.1 (M)** — The body of a document has a maximum of 250 prose words. Prose words are all words outside code blocks, tables, and front matter. The count method of ACE 8.5 applies.

**ACE 15.2 (M)** — The body of a document has a maximum of 80 lines. This count includes code blocks, tables, and blank lines. It excludes the front matter.

**ACE 15.3** — When a document goes above a limit, divide it by topic. Make one document for each topic. Add the new documents to the applicable index.

**ACE 15.4** — Keep each code example small. Show only the lines that are necessary for the topic. Link to the full file in the repository for the rest.

**ACE 15.5** — An agent must find the answer to one question in one document. If a reader must open three documents for one question, the division is wrong. Join or divide again by topic, not by size only.
