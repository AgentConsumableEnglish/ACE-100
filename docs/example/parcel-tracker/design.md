---
"@type": TechArticle
name: Design
description: This document describes the parts of the parcel-tracker service and the data flow.
isPartOf: docs/example/parcel-tracker/README.md
---

# Design

The `parcel-tracker` service records each movement of a parcel as an event. Customer systems send events to the API. Warehouse persons read the position of a parcel from the same API. The service has three parts.

## The parts

The `api` server receives events and answers questions. It writes each event to the database. The `worker` process examines new events and makes position records. The `postgres` database stores the events and the position records. [Use postgres](decisions/use-postgres.md) gives the reason for this database.

## The data flow

An event goes from the customer system to the `api` server. The server writes the event and tells the `worker` through a queue. The `worker` reads the event and updates the position of the parcel. A question to the API reads the position records only. Thus, a slow question does not block the event path.
