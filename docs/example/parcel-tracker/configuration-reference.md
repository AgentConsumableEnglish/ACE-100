---
"@type": APIReference
name: Configuration reference
description: This reference gives the environment variables of the parcel-tracker service.
isPartOf: docs/example/parcel-tracker/README.md
---

# Configuration reference

The service reads these environment variables at the start. A change becomes active after a restart.

## Environment variables

| Name | Type | Default | Meaning |
|---|---|---|---|
| `DATABASE_URL` | `string` | `none` | The connection address of the `postgres` database. Mandatory. |
| `PORT` | `number` | `8080` | The port of the `api` server. |
| `LOG_LEVEL` | `string` | `info` | The minimum level of log records. Values: `debug`, `info`, `error`. |
| `QUEUE_URL` | `string` | `none` | The address of the event queue. Mandatory. |
| `RETRY_LIMIT` | `number` | `5` | The maximum count of tries for one event. |
| `EVENT_TTL_DAYS` | `number` | `90` | The count of days before the deletion of an event. |

**CAUTION:** A decrease of `EVENT_TTL_DAYS` deletes old events at the next cleanup. Make a backup before a decrease.
