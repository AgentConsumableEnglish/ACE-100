---
"@type": TechArticle
genre: rules
name: Section 1 — Words
description: Section 1 gives the two vocabulary layers, technical terms, and backtick quoting.
isPartOf: docs/standard/rules/README.md
---

# Section 1 — Words

**ACE 1.1 (M)** — The vocabulary has two layers:

- The function layer is closed. Use only the function words that the [function core](../../dictionary/README.md) gives. These are the determiners, conjunctions, prepositions, pronouns, and the modality and quantity words.
- The content layer is open. Domain nouns, verbs, adjectives, and adverbs are permitted without an entry. The rules below and [replacements.md](../../dictionary/replacements.md) govern them.

Issue 1 closed the whole vocabulary. Field use showed that no real repository can obey that. [changes.md](../changes.md) gives the record.

**ACE 1.2** — Use one word with one meaning and one part of speech in one repository.

**ACE 1.3** — Use the simple, frequent word for a concept. Do not use a word from the replacements table.

**ACE 1.4** — Permitted forms: plurals, comparatives with "-er" and "-est" or "more" and "most", and the five verb forms that [conventions.md](../../dictionary/conventions.md) gives.

**ACE 1.5 (M)** — Write each code identifier in backticks. This includes commands, flags, paths, filenames, values, and names from code. Backticked text is quoted text. The vocabulary rules do not apply to it.

**ACE 1.6** — A technical term is a name for a real thing in your domain. Declare each technical term in [technical-terms.md](../../dictionary/technical-terms.md), in the same PR that uses it. Do not declare ordinary words as technical terms.

**ACE 1.7** — Do not use a noun as a verb. ("Version the schema" is not correct. Write "Give the schema a version".)

**ACE 1.8** — Use a maximum of three words in a new technical term.

**ACE 1.9** — Do not use slang, jargon, or regional words. ("Nuke the cache" is not correct. Write "Delete the cache".)

**ACE 1.10** — Use one name for each item in all documents. Do not change between names for the same item.

**ACE 1.11** — [Add a word](../../dictionary/add-a-word.md) gives the procedure for the three dictionary changes: a term declaration, a ban, and a function-core extension.

**ACE 1.12 (M)** — Use American English spelling in prose. Do not change the spelling of quoted text, identifiers, or code.
