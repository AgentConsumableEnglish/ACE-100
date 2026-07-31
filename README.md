---
"@type": TechArticle
name: ACE-100 kit
description: This kit contains ACE-100 Issue 1, a controlled language for monorepo documentation, designed for LLM agents.
---

# ACE-100 kit

ACE-100 is Agent-Consumable English. It is a controlled language and a document architecture for monorepos. This kit is Issue 1. The kit obeys its own rules. This file is the root index of the kit.

## Contents

- [The documentation map](docs/README.md). The top index of all governed documents.
- [The standard](docs/standard/README.md). The rules of the language and of the architecture.
- [The dictionary](docs/dictionary/README.md). The approved words and the declared technical terms.
- [The templates](docs/templates/README.md). One start file for each document type.
- [The example](docs/example/README.md). One small package with complete documents.

## Adopt the kit

1. Copy the `docs/` tree into the root of your repository.
2. Make sure that your root `README.md` links to `docs/README.md`.
3. Add the dictionary owners to `CODEOWNERS` for the path `docs/dictionary/`.
4. Read [the checklist](docs/standard/checklist.md) before you write your first document.
5. Write the technical terms of your repository in [technical-terms.md](docs/dictionary/technical-terms.md).

## Root exception

The root index of a repository has no `isPartOf` property. This file is the root of the kit. Thus, this file has no `isPartOf` property.
