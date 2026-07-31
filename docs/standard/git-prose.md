---
"@type": TechArticle
name: Section 16 — Git prose
description: Section 16 gives the rules for commit messages and PR text.
isPartOf: docs/standard/README.md
---

# Section 16 — Git prose

Commit messages and PR text are governed prose. Layer L1 applies to all of it. Layer L2 applies to bodies.

**ACE 16.1 (M)** — Write the commit subject in the imperative. Use a maximum of 15 words. Do not put a period at the end.

**ACE 16.2** — Write the commit body as descriptive text. Tell what the change does and why. Section 6 applies.

**ACE 16.3** — Write the PR description as descriptive text. Give:

- The purpose of the change.
- A link to each document that the change adds or updates.
- The risk, when the change can cause a warning-level result.

**ACE 16.4** — A commit from a tool is exempt. The subject must tell the name of the tool.

**ACE 16.5** — Use the same terms in git prose as in the documents. The dictionary applies.
