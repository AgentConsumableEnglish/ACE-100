---
"@type": TechArticle
name: About ACE-100
description: This document gives the purpose, the sources, and the issue control of ACE-100.
isPartOf: docs/standard/README.md
---

# About ACE-100

ACE-100 is Agent-Consumable English, a controlled language for monorepo documentation, designed for LLM agents. It has two parts. The first part is the rules for words, sentences, documents, and repository structure. The second part is the dictionary: a closed function core, a replacements table, and the declared terms of a repository.

## Purpose

LLM agents read documentation into a limited context window. Excess text decreases the quality of their work and increases cost. Persons read the same documents. ACE-100 makes each document small and clear for the two audiences. When a rule must select one audience, the standard selects the agent.

## Sources

The model for ACE-100 is ASD-STE100 Simplified Technical English, Issue 9 (January 2025). ASD-STE100 is a specification of the AeroSpace and Defence Industries Association of Europe. ACE-100 is not ASD-STE100, and does not claim agreement with it. Issues 2 and 3 also have a second source: two field reports from the migration of a real monorepo. [changes.md](changes.md) records what each report changed.

Issue 3 has a third source: a review of [caveman](https://github.com/JuliusBrussee/caveman), a compression project for agent replies. ACE-100 keeps its own grammar, and [changes.md](changes.md) records what the review changed.

## Issue control

This is the draft of Issue 3. Issue 2 is the last released issue. A change to a rule makes a new issue, and a change to the dictionary does not. Each rule has a stable identifier, for example ACE 5.1. [Enforcement](enforcement.md) gives the identifier format, and [changes.md](changes.md) records the changes between issues.

## Self-compliance

The documents of this standard obey the rules that they give. Quoted examples can show text that does not obey the rules. Declared exemptions are in [the deviations ledger](deviations.md). The standard makes no quantitative claim without a committed measurement. `tools/measure.py` measures the corpus, and each issue commits one snapshot to `tools/measurements/`.
