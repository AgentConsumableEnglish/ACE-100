---
"@type": TechArticle
name: Dictionary conventions
description: This document gives the entry format, the casing rules, and the vocabulary principles.
isPartOf: docs/dictionary/README.md
---

# Dictionary conventions

Each dictionary part is a `DefinedTermSet` document. Each entry is a `DefinedTerm`.

## Entry format

An entry is one table row with three columns:

| Column | Content |
|---|---|
| Word | The approved word, in uppercase letters |
| Part | The part of speech |
| Meaning | The approved meaning, with restrictions and a short example when necessary |

## Casing

Approved words are uppercase in the dictionary only. Write them with normal casing in documents.

## Principles

- One concept has one word. Do not add a synonym of an approved word.
- One word has one meaning. A second meaning is not permitted.
- A word with two parts of speech has one entry for each part.
- Plural forms of approved nouns are approved (ACE 1.4).
- Comparative forms of approved adjectives are approved: with "-er" and "-est", or with "more" and "most".
- These verb forms are approved: infinitive, imperative, simple present, simple past, past participle.
- An entry can have a `sameAs` link to an external definition. This is optional.

## Sources

The principles come from ASD-STE100 Issue 9, part 2. The words are the ACE-100 core, not the ASD-STE100 dictionary.
