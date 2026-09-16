from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from woobe import Woobe
from woobe._transport.sse import SseFrame
from woobe.errors import WoobeConnectionError, WoobeRecoveryError


class _FakeTransport:
    def __init__(self, *, disconnect_once: bool = False, fail_before_identity: bool = False) -> None:
        self.disconnect_once = disconnect_once
        self.fail_before_identity = fail_before_identity
        self.calls: list[str] = []
        self.idempotency_keys: list[str] = []

    async def aclose(self) -> None:
        return None

    async def resolve_active_run(self, *, key: str, session_id: str) -> str | None:
        del key, session_id
        self.calls.append("active")
        return None

    async def stream_new_run(
        self,
        *,
        key: str,
        message: str,
        session_id: str | None,
        idempotency_key: str,
    ) -> AsyncIterator[SseFrame]:
        del key, message, session_id
        self.calls.append("new")
        self.idempotency_keys.append(idempotency_key)

        if self.fail_before_identity:
            raise WoobeConnectionError("connection lost")

        yield SseFrame(
            event="meta",
            data={
                "type": "meta",
                "run_id": "run-1",
                "session_id": "session-1",
            },
        )
        yield SseFrame(
            event="token",
            event_id="1",
            data={
                "type": "token",
                "run_id": "run-1",
                "session_id": "session-1",
                "content": "Olá",
            },
        )

        if self.disconnect_once:
            self.disconnect_once = False
            raise WoobeConnectionError("connection lost")

        yield SseFrame(
            event="done",
            event_id="2",
            data={
                "type": "done",
                "run_id": "run-1",
                "session_id": "session-1",
                "answer": "Olá",
            },
        )

    async def stream_run(self, *, key: str, run_id: str) -> AsyncIterator[SseFrame]:
        del key
        assert run_id == "run-1"
        self.calls.append("reattach")
        yield SseFrame(
            event="run.state",
            event_id="2",
            data={
                "type": "run.state",
                "run_id": "run-1",
                "session_id": "session-1",
                "sequence": 2,
                "status": "running",
                "output": "Olá",
            },
        )
        yield SseFrame(
            event="done",
            event_id="3",
            data={
                "type": "done",
                "run_id": "run-1",
                "session_id": "session-1",
                "answer": "Olá!",
            },
        )


@pytest.mark.asyncio
async def test_events_start_the_request_and_yield_identified_woobe_events() -> None:
    transport = _FakeTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")
    chat = agent.chat(input="Olá")

    assert transport.calls == []

    events = [event async for event in chat.events()]

    assert transport.calls == ["new"]
    assert [event.type for event in events] == ["meta", "token", "done"]
    assert all(event.run_id == "run-1" for event in events)
    assert all(event.session_id == "session-1" for event in events)
    assert chat.run_id == "run-1"
    assert chat.session_id == "session-1"


@pytest.mark.asyncio
async def test_transport_disconnect_reattaches_same_run_without_second_post() -> None:
    transport = _FakeTransport(disconnect_once=True)
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    events = [event async for event in agent.chat(input="Olá").events()]

    assert transport.calls == ["new", "reattach"]
    assert [event.type for event in events] == ["meta", "token", "run.state", "done"]


@pytest.mark.asyncio
async def test_agent_initial_failure_fails_closed_instead_of_reposting() -> None:
    transport = _FakeTransport(fail_before_identity=True)
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    with pytest.raises(WoobeRecoveryError):
        _ = [event async for event in agent.chat(input="Olá").events()]

    assert transport.calls == ["new"]
