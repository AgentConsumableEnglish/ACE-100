---
"@type": TechArticle
name: ACE-100 kit
description: This kit contains ACE-100, a controlled language for monorepo documentation, designed for LLM agents.
---

# ACE-100 kit

ACE-100 is Agent-Consumable English. It is a controlled language and a document architecture for monorepos. This kit is Issue 3. The kit obeys its own rules. This file is the root index of the kit.

## Contents

- [The documentation map](docs/README.md). The top index of all governed documents.
- [The standard](docs/standard/README.md). The rules of the language and of the architecture.
- [The dictionary](docs/dictionary/README.md). The function core, the replacements, and the declared terms.
- [The templates](docs/templates/README.md). One start file for each document type.
- [The example](docs/example/README.md). One small package with complete documents.
- [The tools](tools/README.md). The conformance checkers and the measurement tool.

## Adopt the kit

Run the adopt command from the root of your repository:

```bash
curl -fsSL https://github.com/AgentConsumableEnglish/ACE-100/releases/latest/download/adopt.sh | sh
```

The command copies the `docs/` and `tools/` trees, links your root `README.md` to the documentation map, and runs the checkers. A later run upgrades the kit to the newest issue, and it keeps your own documents. An issue argument, for example `issue-2`, pins one issue. The `--owners` flag writes the dictionary owners to a `CODEOWNERS` file. The `--migrate` flag installs the `ace-migrate` skill, for an agent rewrite of an existing repository.

After the command:

1. Write the technical terms of your repository in [technical-terms.md](docs/dictionary/technical-terms.md).
2. Give each writer [the agent brief](docs/standard/agent-brief.md).
3. Run `tools/check.sh` from the first document (ACE 18.1).
4. For a rewrite of an existing repository, read [Migration](docs/standard/migration.md) first.

## Root exception

The root index of a repository has no `isPartOf` property. This file is the root of the kit. Thus, this file has no `isPartOf` property.
