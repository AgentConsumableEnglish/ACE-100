---
"@type": TechArticle
genre: rules
name: The reader brief
description: This document gives the read side of ACE-100 in one file, for an agent that consumes a governed corpus.
isPartOf: docs/standard/README.md
---

# The reader brief

[The agent brief](agent-brief.md) is for a writer. This one is for a reader. Read it once, then read the corpus. [Section 19](reading.md) gives the rules that it summarizes.

## What a governed corpus gives you

- Every document opens with front matter: `"@type"`, `name`, `description`, and `isPartOf` (ACE 13.2).
- The `description` is one sentence, 20 words maximum. It tells you what the document is.
- Every directory has one `README.md` index (ACE 11.3). The index names each document in that directory, with one line for each.
- `isPartOf` names the parent index. The chain of parents reaches the root index of the repository.
- One fact lives in one document (ACE 14.7). A second copy of a fact is a defect, not a convenience.
- A document is 120 body lines maximum (ACE 15.1). A large topic is a directory of parts, not a long file.

## How to read it

1. Start at the index of the directory that your task names.
2. Read descriptions before documents. `tools/describe.sh` prints one row for each document.
3. Open a document when your task needs a fact that its description names.
4. Read the whole document before you change it.

```bash
tools/describe.sh docs           # path and description, every document under docs
tools/describe.sh docs migrate   # the rows that match "migrate"
```

Without the tool, two commands read one document in parts:

```bash
awk '/^---$/{n++} n<2' <file>            # the front matter alone
awk 'f; /^---$/{n++} n==2{f=1}' <file>   # the body, without the front matter
```

## Comments are governed too

- A comment states what is true of its own file (ACE 10.7).
- A fact true across files lives in a document, and the comment cites it.
- A citation in a comment points at a shared fact. Follow it when your task needs that fact.
- A backticked path in a comment resolves, exactly as it does in a document (ACE 14.9).

## What not to do

- Do not copy a description into the place that cites the document (ACE 19.4). The copy goes stale, and ACE 14.7 forbids it.
- Do not treat a description as a substitute for the document. It is a pointer.
- Do not conclude that a corpus is empty because a probe returned nothing. Check the command first.

## What this brief does not claim

No committed measurement settles what this protocol costs or saves. [About ACE-100](about.md) forbids a quantitative claim without a measurement. The ground for these rules is that the corpus already carries a description and an index.
