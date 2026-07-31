---
"@type": TechArticle
name: Section 12 — Document types
description: Section 12 gives the five document types, their schema.org names, and their rule bindings.
isPartOf: docs/standard/architecture/README.md
---

# Section 12 — Document types

**ACE 12.1 (M)** — Every document has exactly one type. The `@type` value is one of five schema.org names.

| `@type` | Function | Rule binding | Template |
|---|---|---|---|
| `CollectionPage` | Index of a directory | Section 11 | [collection-page.md](../../templates/collection-page.md) |
| `TechArticle` | Description of one topic | Section 6 | [tech-article.md](../../templates/tech-article.md) |
| `HowTo` | Procedure with steps | Section 5 | [how-to.md](../../templates/how-to.md) |
| `APIReference` | Reference data, mostly tables | Section 6 | [api-reference.md](../../templates/api-reference.md) |
| `DefinedTermSet` | Dictionary part | Section 6 | [defined-term-set.md](../../templates/defined-term-set.md) |

**ACE 12.2 (M)** — A decision record is a `TechArticle` with the property `genre: decision-record`. [The template](../../templates/decision-record.md) gives its form.

**ACE 12.3** — Do not mix types in one document. If a description and a procedure are necessary for one topic, write two documents.

**ACE 12.4** — A dictionary entry is a `DefinedTerm` in a `DefinedTermSet` document. [The dictionary](../../dictionary/README.md) gives the entry format.
