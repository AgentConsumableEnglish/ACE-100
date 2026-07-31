---
"@type": TechArticle
genre: rules
name: Section 11 — Layout
description: Section 11 tells where documents live in the monorepo and how indexes route readers.
isPartOf: docs/standard/architecture/README.md
---

# Section 11 — Layout

**ACE 11.1** — Keep the documents of a package in the directory of that package. The documents change in the same PR as the code that they describe.

**ACE 11.2** — Keep documents that apply to the whole repository under the root `docs/` tree. Examples: deployment topics, conventions, this standard, and the dictionary.

**ACE 11.3 (M)** — Every governed directory has exactly one index document. The index is `README.md`, with the type `CollectionPage`.

**ACE 11.4** — An index lists the documents and the indexes of its directory. Each entry has a link and a one-line purpose. One short paragraph before the list is permitted. An index does not give other content.

**ACE 11.5** — The root `README.md` of the repository links to `docs/README.md`. A reader goes from the root to any document through indexes only.

**ACE 11.6** — When you add a document, add its entry to the index of its directory in the same PR.
