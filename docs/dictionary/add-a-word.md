---
"@type": HowTo
name: Add a word
description: This procedure adds a word to the dictionary in the same PR that needs it.
isPartOf: docs/dictionary/README.md
---

# Add a word

Do this procedure when a necessary word is not in the dictionary.

1. Read [replacements.md](replacements.md) and make sure that the word is not there.
2. Search the core parts for an approved word with the same concept.
3. If an approved word covers the concept, use that word and stop here.
4. If the word is a name for a real thing, add it to [technical-terms.md](technical-terms.md).
5. For all other words, add an entry to the applicable core part.
6. Write the part of speech and a meaning of one sentence.
7. If the word replaces a word that is not permitted, add a replacements row.
8. Put the dictionary change and your text in the same PR.
9. Tell the dictionary owners in the PR description.

**CAUTION:** Do not add a synonym of an approved word. Synonyms cause different names for one concept. The owners will refuse the PR.
