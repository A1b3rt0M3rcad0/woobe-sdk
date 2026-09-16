# Runtime streaming and reattach

## Lazy execution

Creating a Chat does not perform network I/O:

```python
chat = agent.chat(input="Olá")
```

The first Runtime API request starts only when the async generator returned by `events()` begins iteration:

```python
async for event in chat.events():
    ...
```

This keeps side effects explicit and prevents a Run from starting merely because an object was constructed.

## Initial request

The SDK translates the public Python shape into the Woobe Runtime API contract:

```text
agent.chat(input="Olá", session_id=...)
              |
              v
POST /v1/run/stream
{
  "message": "Olá",
  "session_id": "..."
}
```

Agent and Network Runtime Keys use the same public Runtime API surface. The server resolves the target from the key binding.

## Canonical identity

As Runtime frames arrive, the SDK records the canonical `run_id` and `session_id`. Frames received before both identities are known are not exposed as partially identified `WoobeEvent` objects.

Once known, identity is immutable for the Chat. A stream that changes Run or Session identity is a protocol error.

## Sequence semantics

Logical sequence belongs to the runtime protocol; transport cursors do not.

For incremental frames:

- sequence `<=` the last accepted sequence is stale/duplicate and is ignored;
- sequence `> last + 1` is a gap and causes reattach/reconciliation;
- contiguous sequence advances the local high watermark.

For `run.state`, a newer snapshot may advance directly to its high watermark because it is a replacement projection. A durable-only snapshot with `realtime_available=false` is accepted without rewinding the last known realtime sequence.

## Reattach

After `run_id` is known, a broken SSE connection becomes observation recovery:

```text
stream interrupted
      |
      v
GET /v1/runs/{run_id}/stream
      |
      v
run.state @ high watermark
      |
      v
live events after the snapshot
```

The SDK never starts another Agent Run to repair transport.

If the SDK knows a Session but lost the Run pointer, it first asks:

```text
GET /v1/sessions/{session_id}/active-run
```

and then attaches to the returned Run.

## Initial-create failure window

The dangerous window is a connection failure after the server may have accepted work but before the client has learned the canonical Run identity.

For Agent runtime, the current public create contract does not yet provide a general idempotency guarantee for that window. The SDK therefore fails closed instead of automatically POSTing the same logical request again.

Network runtime currently supports an idempotency key. The SDK creates one key per Chat and reuses it if the initial Network create-and-stream request must be retried before a Run ID is known.

## Terminal events

Terminal runtime events/states end `events()` normally. An Agent or Network execution failure remains a runtime event/state and is not confused with a transport exception. SDK exceptions represent client, protocol, authentication or recovery failures.
