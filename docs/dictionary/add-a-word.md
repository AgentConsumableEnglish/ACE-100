---
"@type": HowTo
name: Add a word
description: This procedure changes the function core, the replacements table, or the technical terms.
isPartOf: docs/dictionary/README.md
---

# Add a word

Content words do not go into the dictionary. Do this procedure only for these three cases.

## Declare a technical term

1. Make sure that the word is a name for a real thing (ACE 1.6).
2. Add a row to [technical-terms.md](technical-terms.md), in its category.
3. Put the change in the same PR that uses the term.

## Ban a word

1. Make sure that an approved or simpler word carries the concept.
2. Add a row to [replacements.md](replacements.md) with the alternative.
3. Tell the dictionary owners in the PR description.

## Extend the function core

1. Make sure that the word is a function word, not a content word.
2. Search the two function parts for a word with the same concept.
3. If no word covers the concept, add an entry with part of speech and meaning.
4. Tell the dictionary owners in the PR description.

**CAUTION:** Do not add a synonym of a function word. Synonyms cause different names for one concept. The owners will refuse the PR.
