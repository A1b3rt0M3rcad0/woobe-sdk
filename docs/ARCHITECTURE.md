# Architecture

## Purpose

Woobe SDK is the Python application boundary for consuming a Woobe Agent or Agent Network. It should make production runtime consumption small without copying production runtime complexity into the application.

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

The first public surface is deliberately small:

```text
Woobe
  |
  `-- connect
       |-- agent(alias, key)
       `-- network(alias, key)
              |
              `-- chat(input, session_id?)
                         |
                         `-- events() -> AsyncIterator[WoobeEvent]
```

`alias` is an application-side label. Runtime routing and authorization are determined by the Runtime Key issued by Woobe.

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

The SDK owns transport and consumption behavior only. It may serialize requests, authenticate with Runtime Keys, parse SSE, normalize public events, reject stale/duplicate sequences, detect gaps and reattach an existing Run.

The SDK must not own model selection, Tool execution, RAG, Context Engineering, execution strategies, Run finalization or durable business truth. Those responsibilities belong to Woobe.

## Event contract

`WoobeEvent` is the Python representation of a runtime event. It is not a new source of event semantics.

The SDK guarantees that every event it yields has `session_id`, `run_id`, `run_kind`, `type` and `payload`. Optional event metadata is populated only when the Runtime API supplies it. Missing metadata is never fabricated.

The current `chat()` primitive is intentionally session-backed. A future non-conversational/stateless execution primitive should be modeled separately instead of weakening Chat semantics.

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
