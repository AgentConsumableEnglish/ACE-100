---
"@type": TechArticle
genre: decision-record
name: Use postgres
description: This record gives the decision to use postgres as the primary database.
isPartOf: docs/example/parcel-tracker/decisions/README.md
---

# Use postgres

## Status

Accepted, 2026-07-01.

## Context

The service must store events and position records. Transactions are necessary, because one event updates two tables. The team operates SQL databases at this time. A new database type increases the operational risk.

## Decision

We will use `postgres` version 16 as the primary database. We will use one database for events and position records.

## Results

The team keeps its known tools, and the operational risk stays low. Transactions make the two-table updates safe. The event table will become large. Thus, the `EVENT_TTL_DAYS` cleanup is mandatory from the start.
