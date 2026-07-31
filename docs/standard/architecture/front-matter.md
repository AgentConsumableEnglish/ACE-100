---
"@type": TechArticle
genre: rules
name: Section 13 — Front matter
description: Section 13 gives the mandatory YAML front matter and its schema.org properties.
isPartOf: docs/standard/architecture/README.md
---

# Section 13 — Front matter

**ACE 13.1 (M)** — Every document starts with a YAML front-matter block. The block gives schema.org properties.

**ACE 13.2 (M)** — These properties are mandatory:

| Property | Value |
|---|---|
| `"@type"` | One of the five type names (ACE 12.1) |
| `name` | The title of the document |
| `description` | One sentence that gives the purpose, 20 words maximum |
| `isPartOf` | The path of the parent index, from the repository root |

**ACE 13.3** — The root index of the repository omits `isPartOf`. All other documents have it.

**ACE 13.4** — The context `https://schema.org` applies to all front matter in the repository. This rule declares it once. Do not write `@context` in each file.

**ACE 13.5** — Optional properties are permitted when they are accurate. Examples: `genre`, `about`, `sameAs`, `termCode`.

**ACE 13.6 (M)** — The H1 of the body is equal to the `name` property.

**ACE 13.7 (M)** — The `exempt` property declares the rules that a document does not obey. Give the rule identifiers and a short reason. Each exemption must have a row in [the deviations ledger](../deviations.md). A checker does not apply an exempted rule to that document.

**ACE 13.8** — Front matter changes the first line of a file. Tools that read line 1 will break. [Migration](../migration.md) gives the warning and the repair steps.

## Example

```yaml
---
"@type": HowTo
name: Deploy to production
description: This procedure deploys the service to production.
isPartOf: docs/example/parcel-tracker/README.md
---
```
