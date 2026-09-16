# Woobe SDK

Python SDK for consuming Agents and Agent Networks running on the Woobe Runtime API.

The SDK is intentionally a **runtime client**, not a second control plane and not an agent framework. Agent configuration, Releases, Tools, Knowledge, execution strategies and runtime infrastructure remain server-side in Woobe. Applications connect to an already published runtime target and consume its execution events.

> **Pre-release:** the SDK is being initialized together with the Woobe public runtime contract. Public APIs can still change before the first stable release.

## Quick start

```python
from woobe import Woobe


woobe = Woobe()

agent = woobe.connect.agent(
    alias="support",
    key="...",
)

# No HTTP request is executed here.
chat = agent.chat(
    input="Olá",
)

# The Runtime request starts when events() is actually iterated.
async for event in chat.events():
    # event is always a WoobeEvent.
    print(event.type, event.payload)
```

To continue the same conversation, reuse the Session returned by the previous interaction:

```python
chat = agent.chat(
    input="Continue de onde paramos",
    session_id=previous_chat.session_id,
)

async for event in chat.events():
    print(event)
```

The same surface is available for Networks:

```python
network = woobe.connect.network(
    alias="sales-network",
    key="...",
)

chat = network.chat(input="Qual é o próximo passo?")

async for event in chat.events():
    print(event)
```

## Runtime model

The public SDK surface follows four concepts:

```text
Target   -> Agent or Network
Session  -> conversational continuity
Run      -> one finite logical execution
Event    -> what happened during that Run
```

`agent.chat(...)` and `network.chat(...)` only construct a lazy `Chat`. Network activity starts when `chat.events()` is iterated.

Every event yielded by `Chat.events()` is a `WoobeEvent` associated with the canonical Session and Run:

```python
from woobe.events import WoobeEvent

async for event in chat.events():
    event.session_id
    event.run_id
    event.run_kind
    event.sequence
    event.type
    event.payload
```

The SDK preserves Woobe runtime event names and payloads. It does not invent a second event ontology.

## Reattach and duplicate-Run safety

A stream connection is an observer of a Run; it does not own the Run.

Once the canonical `run_id` is known, a transport interruption is recovered through the Woobe reattach endpoint for the **same Run**. The SDK does not submit a second Agent execution merely because SSE disconnected.

```text
POST /v1/run/stream
        |
        v
 canonical run_id
        |
   connection loss
        |
        v
GET /v1/runs/{run_id}/stream
        |
        v
     same Run
```

If only the Session is known, the SDK can resolve the active Run through `/v1/sessions/{session_id}/active-run` before reattaching. Network initial retries reuse one idempotency key because the current Network public runtime supports that contract. Agent recovery fails closed if the initial connection dies before either Run or Session identity can be recovered; retrying an unsafe POST could create a second logical execution.

## `WoobeEvent`

```python
class WoobeEvent(BaseModel):
    event_id: str | None
    session_id: str
    run_id: str
    run_kind: Literal["AGENT", "NETWORK"]
    sequence: int | None
    type: str
    occurred_at: datetime | None
    scope_type: str | None
    scope_id: str | None
    payload: dict[str, Any]
```

`session_id` and `run_id` are mandatory on events exposed to application code. Fields that are not yet uniformly exposed by every Woobe runtime frame, such as `event_id`, `occurred_at` and scope metadata, remain optional rather than being fabricated by the SDK.

## Configuration

The default hosted endpoint is `https://api.woobe.com.br`. Self-hosted environments can provide a base URL explicitly or through `WOOBE_BASE_URL`:

```python
woobe = Woobe(
    base_url="https://woobe.internal.example",
)
```

For long-lived processes, close the underlying async HTTP client on shutdown:

```python
await woobe.aclose()
```

or use an async context manager:

```python
async with Woobe() as woobe:
    agent = woobe.connect.agent(alias="support", key="...")
    async for event in agent.chat(input="Olá").events():
        print(event)
```

## Repository

```text
src/woobe/          public SDK and private transport implementation
tests/              SDK unit tests
examples/           small executable usage examples
docs/               architecture and runtime contract documentation
```

Start with [`docs/README.md`](docs/README.md) for the documentation index.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
```

The integration branch is `master`. Feature and fix branches should start from `master` and target `master` through focused pull requests.
