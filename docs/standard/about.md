---
"@type": TechArticle
name: About ACE-100
description: This document gives the purpose, the sources, and the issue control of ACE-100.
isPartOf: docs/standard/README.md
---

# About ACE-100

ACE-100 is Agent-Consumable English, a controlled language for monorepo documentation, designed for LLM agents. It has two parts. The first part is the rules for words, sentences, documents, and repository structure. The second part is the dictionary, a closed vocabulary that authors extend in the repository.

## Purpose

LLM agents read documentation into a limited context window. Excess text decreases the quality of their work and increases cost. Persons read the same documents. ACE-100 makes each document small and clear for the two audiences. When a rule must select one audience, the standard selects the agent.

## Sources

The model for ACE-100 is ASD-STE100 Simplified Technical English, Issue 9 (January 2025). ASD-STE100 is a specification of the AeroSpace and Defence Industries Association of Europe. ACE-100 is not ASD-STE100, and does not claim agreement with it. ACE-100 has its own dictionary and smaller limits. The document types come from the schema.org vocabulary.

## Issue control

This is Issue 1. A change to a rule makes a new issue. A change to the dictionary does not make a new issue. Each rule has a stable identifier, for example ACE 5.1. [Enforcement](enforcement.md) gives the identifier format.

## Self-compliance

The documents of this standard obey the rules that they give. Quoted examples can show text that does not obey the rules.
