# Contributing to Woobe SDK

Woobe SDK uses `master` as the integration branch.

## Workflow

1. Start a focused `feature/`, `fix/`, `chore/` or `docs/` branch from the latest `master`.
2. Keep the change scoped to one SDK concern.
3. Preserve the public API unless the change intentionally modifies a documented contract.
4. Add or update tests for changed runtime behavior.
5. Update documentation when public behavior changes.
6. Open a pull request targeting `master`.
7. Do not merge without explicit maintainer approval.

## SDK boundary

The SDK is a client for the Woobe Runtime API. It must not become another execution engine.

Keep these responsibilities server-side in Woobe:

- Agent and Network orchestration;
- model/provider selection;
- Tools and MCP execution;
- Knowledge/RAG;
- Context Engineering;
- releases and environment rules;
- runtime lifecycle truth and durable Run state.

The SDK may own client-side concerns such as authentication headers, request serialization, SSE parsing, event normalization, safe reattach, bounded transport retry and typed errors.

## Runtime invariants

A connection observes a Run; it does not own it. Once a canonical Run ID is known, transport recovery must reattach to that Run instead of creating another logical execution.

Do not add automatic retry behavior that can duplicate a Run. Any retry of a create operation must be protected by a server-supported idempotency contract.

The SDK must not rename or reinterpret Woobe runtime event semantics. `WoobeEvent` is the client representation of the public runtime event contract, not a parallel event system.

## Public API discipline

Keep the main integration surface small and predictable:

```python
woobe = Woobe()
agent = woobe.connect.agent(alias="support", key="...")
chat = agent.chat(input="Olá")

async for event in chat.events():
    ...
```

Do not add aliases such as `ask()`, `send()`, `invoke()`, `execute()` and `complete()` for the same operation without a concrete use case. New methods should represent materially different semantics.

## Quality

The local development checks are:

```bash
pytest
ruff check .
```

Do not claim a check passed unless it was actually executed.
