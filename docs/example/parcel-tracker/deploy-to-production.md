---
"@type": HowTo
name: Deploy to production
description: This procedure releases the parcel-tracker service to production.
isPartOf: docs/example/parcel-tracker/README.md
---

# Deploy to production

Do this procedure after a release approval. The procedure takes about 20 minutes.

## Before you start

- Make sure that the pipeline for your commit is green.
- Make sure that you have the `deployer` role.
- Make sure that staging ran your commit for 30 minutes minimum.

## Steps

1. Run `make release-notes` and read the output.
2. Run `make deploy ENV=production`.
3. Wait until the dashboard shows the new version on all nodes.

**WARNING:** Do not run `make migrate ENV=production` before a database backup. The migration changes tables, and old data is not recoverable.

4. When the schema changed in this release, run `make backup` first, then `make migrate ENV=production`.
5. Run `make smoke ENV=production`. The output must show `PASS`.
6. Tell the team in the release channel.

## If the deployment fails

1. Run `make revert ENV=production`.
2. Make sure that the dashboard shows the last version again.
3. Write the failure and the time in the release channel.
