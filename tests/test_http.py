from __future__ import annotations

import json

import httpx
import pytest

from woobe._transport.http import RuntimeTransport


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("external_context", "expected_payload"),
    [
        (None, {"message": "Olá"}),
        ({}, {"message": "Olá", "external_context": {}}),
        (
            {"customer_id": "customer-123", "preferences": {"language": "pt-BR"}},
            {
                "message": "Olá",
                "external_context": {
                    "customer_id": "customer-123",
                    "preferences": {"language": "pt-BR"},
                },
            },
        ),
    ],
)
async def test_stream_new_run_serializes_external_context(
    external_context: dict | None,
    expected_payload: dict,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["idempotency_key"] = request.headers.get("Idempotency-Key")
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=b"",
        )

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        frames = [
            frame
            async for frame in transport.stream_new_run(
                key="runtime-key",
                message="Olá",
                session_id=None,
                external_context=external_context,
                idempotency_key="run-idempotency",
            )
        ]
    finally:
        await transport.aclose()

    assert frames == []
    assert captured["payload"] == expected_payload
    assert captured["idempotency_key"] == "run-idempotency"
