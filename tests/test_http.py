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


@pytest.mark.asyncio
async def test_validate_output_context_calls_public_validator() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("Authorization")
        captured["accept"] = request.headers.get("Accept")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "valid": False,
                    "target_type": "agent",
                    "target_id": "agent-1",
                    "environment": "production",
                    "release_id": "release-1",
                    "release_version": "v2.0.0",
                    "expected_output_context": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                    "received_output_context": {
                        "type": "object",
                        "properties": {"message": {"type": "integer"}},
                        "required": ["message"],
                    },
                    "expected_hash": "expected",
                    "received_hash": "received",
                    "issues": [
                        {
                            "code": "OUTPUT_CONTEXT_MISMATCH",
                            "message": "SDK output_context does not match",
                        }
                    ],
                },
            },
        )

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        data = await transport.validate_output_context(
            key="runtime-key",
            output_context={
                "type": "object",
                "properties": {"message": {"type": "integer"}},
                "required": ["message"],
            },
        )
    finally:
        await transport.aclose()

    assert captured == {
        "path": "/v1/output-context/validate",
        "authorization": "Bearer runtime-key",
        "accept": "application/json",
        "payload": {
            "output_context": {
                "type": "object",
                "properties": {"message": {"type": "integer"}},
                "required": ["message"],
            }
        },
    }
    assert data["valid"] is False
    assert data["issues"][0]["code"] == "OUTPUT_CONTEXT_MISMATCH"


@pytest.mark.asyncio
async def test_validate_output_context_rejects_invalid_response_envelope() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = RuntimeTransport(base_url="https://runtime.test", timeout_seconds=1)
    transport._client = httpx.AsyncClient(
        base_url="https://runtime.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(Exception, match="invalid envelope"):
            await transport.validate_output_context(
                key="runtime-key",
                output_context=None,
            )
    finally:
        await transport.aclose()
