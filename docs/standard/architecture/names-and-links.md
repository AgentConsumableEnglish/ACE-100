---
"@type": TechArticle
genre: rules
name: Section 14 — Names and links
description: Section 14 gives the rules for file names, headings, and links.
isPartOf: docs/standard/architecture/README.md
---

# Section 14 — Names and links

**ACE 14.1 (M)** — Give each document a `kebab-case` filename with the extension `.md`. The name gives the one topic of the document. Example: `deploy-to-production.md`.

**ACE 14.2 (M)** — The index of a directory is `README.md`. No other document has this name.

**ACE 14.3 (M)** — Use headings H1 to H3 only. A document that must have H4 is too large. Divide it.

**ACE 14.4** — Write body links relative to the file that contains them. Write front-matter paths from the repository root.

**ACE 14.5 (M)** — Link to a specific file, never to a directory.

**ACE 14.6** — When a document moves, update all links to it in the same PR.

**ACE 14.7** — Do not repeat the content of another document. Link to it. One fact lives in one document.

**ACE 14.8** — Do not move or rename a file whose path an external system references. Examples: commit trailers, test assertions, published links. Declare the path exempt (ACE 13.7) and keep it. A rename that orphans history is a larger loss than a broken convention.

**ACE 14.9 (M)** — A backticked span that contains `/` names a repository path. The path must resolve from the repository root or from the document. A backticked path is an identifier and a pointer at the same time. ACE 1.5 exempts it from the word rules only, never from resolution.

Two shapes are outside this rule: a placeholder in angle brackets, and a span with spaces. When an example must show a path that has no file, declare the exemption (ACE 13.7). Field data: four conforming divisions left 101 stale backticked paths, and no check saw one of them.
