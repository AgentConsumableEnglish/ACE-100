---
"@type": TechArticle
name: Dictionary conventions
description: This document gives the entry format, the casing rules, and the vocabulary principles.
isPartOf: docs/dictionary/README.md
---

# Dictionary conventions

Each dictionary part is a `DefinedTermSet` document. Each entry is a `DefinedTerm`, one table row: the word in uppercase, the part of speech, and the meaning. Write approved words with normal casing in documents.

## The two layers

The function core is closed. It holds the words that give structure: determiners, conjunctions, prepositions, pronouns, modality, quantity, and time. Do not use a function word that the core does not give.

The content layer is open. Domain nouns, verbs, adjectives, and adverbs are permitted without an entry. Style rules govern them:

- One name for each item, in all documents (ACE 1.10).
- Do not use a word from [replacements.md](replacements.md).
- Use the simple, frequent word for a concept.
- Use one meaning for one word in one repository.

## Forms

- Plural forms of nouns are permitted.
- Comparative forms of adjectives are permitted: with "-er" and "-est", or with "more" and "most".
- Permitted verb forms: infinitive, imperative, simple present, simple past, past participle.

## Sources

The principles come from ASD-STE100 Issue 9, part 2. The split into two layers comes from field use (see [changes.md](../standard/changes.md)).
