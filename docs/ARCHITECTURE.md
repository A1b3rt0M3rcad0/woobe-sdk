# Architecture

## Purpose

Woobe SDK is the Python application boundary for consuming a Woobe Agent or Agent Network. It keeps production Runtime consumption small without copying server-side execution complexity into the application.

```text
application
    |
    v
Woobe Python SDK
    |
    v
Woobe Runtime API
    |
    +-- Agent Runtime
    `-- Network Runtime
```

The SDK does not execute Agents locally.

## Public surface

```text
Woobe
  |
  `-- connect
       |-- agent(alias, key)
       `-- network(alias, key)
              |
              |-- validate_output_context(model_or_schema)
              |
              `-- chat(input, session_id?, external_context?)
                         |
                         `-- events() -> AsyncIterator[WoobeEvent]
```

`alias` is an application-side label. Runtime routing and authorization are determined by the Runtime Key issued by Woobe.

Output Context validation is a preflight client boundary. The SDK may translate a local Pydantic model into JSON Schema and call the Runtime validator, but Woobe remains authoritative for the published Release contract and compatibility result.

## Package layout

```text
src/woobe/
├── __init__.py
├── client.py
├── connect.py
├── targets.py
├── chat.py
├── events.py
├── errors.py
└── _transport/
    ├── http.py
    └── sse.py
```

Public domain concepts stay at the package root. HTTP and SSE mechanics remain private under `_transport`.

## Boundary rules

The SDK owns transport and consumption behavior only. It may serialize requests, authenticate with Runtime Keys, decode SSE, validate Runtime Protocol v2, reject stale/duplicate sequences, detect gaps and reattach an existing Run.

The SDK must not own model selection, Tool execution, RAG, Context Engineering, execution strategies, Run finalization or durable business truth. Those responsibilities belong to Woobe.

## Runtime Protocol v2 boundary

The Runtime exposes two frame categories.

Semantic events are canonical and self-contained:

```text
protocol_version = 2
event_id
run_id
session_id
run_kind
sequence
type
occurred_at
payload
```

`WoobeEvent` is a typed representation of that exact semantic contract. The SDK does not recover identity from legacy aliases, does not move arbitrary top-level fields into `payload`, and does not fabricate missing sequence or timestamps.

Transport/control frames are intentionally different. Heartbeats, realtime-degradation notices and pre-Acceptance failures have no semantic Run identity. They remain internal to transport handling and are not yielded as `WoobeEvent`.

This distinction keeps the public iterator semantically strong: application code receiving a `WoobeEvent` always has complete Run and Session identity.

## Chat responsibilities

`Chat` is lazy and stateful only as a client-side observer:

```text
construct Chat
    |
    | no request
    v
iterate events()
    |
    v
POST create-and-observe
    |
    +-- remember canonical run_id/session_id
    +-- validate run_kind
    +-- enforce logical sequence
    +-- yield semantic WoobeEvent
    |
 transport loss
    |
    v
GET reattach same Run
```

Once identity is known, a stream cannot change Run, Session or Run kind. A violation is a protocol error.

## Dependency direction

```text
client/connect/targets
        |
        v
       Chat
      /    \
     v      v
 WoobeEvent  private transport
```

Private transport code must not define product-domain behavior. Public types must not expose `httpx` response objects, Redis cursors or server implementation details.
