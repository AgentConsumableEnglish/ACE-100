---
"@type": TechArticle
name: Section 7 — Safety
description: Section 7 gives the rules for WARNING and CAUTION text in software procedures.
isPartOf: docs/standard/rules/README.md
---

# Section 7 — Safety

A warning gives a risk of harm that is permanent or externally visible. Examples: data loss, a production outage, a security exposure, or a cost that you cannot recover. A caution gives a risk of damage that the team can repair. Examples: broken local state or lost work time. If the two risks apply, use a warning.

**ACE 7.1 (M)** — Start the text with the level word. Write `**WARNING:**` or `**CAUTION:**` at the start of the line.

**ACE 7.2** — Make the decision from a risk analysis each time, not from usual practice.

**ACE 7.3** — After the level word, write a clear command or condition. Write the condition first when the reader must know it before the action.

**ACE 7.4** — Give the specific risk if the reader does not obey. An abstract statement does not make readers careful.

**ACE 7.5** — Do not put safety text in a note. Put it immediately before the applicable step.

## Example

**WARNING:** Do not run `migrate --drop` against production. This command deletes all tables, and the data is not recoverable.
