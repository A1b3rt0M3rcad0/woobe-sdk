from __future__ import annotations

import pytest
from pydantic import BaseModel

from woobe import Woobe


class SupportOutput(BaseModel):
    message: str
    confidence: float


class _ContractTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def validate_output_context(self, *, key: str, output_context: dict | None) -> dict:
        self.calls.append(
            {
                "key": key,
                "output_context": output_context,
            }
        )
        return {
            "valid": True,
            "target_type": "agent",
            "target_id": "agent-1",
            "environment": "production",
            "release_id": "release-1",
            "release_version": "v1.0.0",
            "expected_output_context": output_context,
            "received_output_context": output_context,
            "expected_hash": "same-hash",
            "received_hash": "same-hash",
            "issues": [],
        }


def test_chat_is_lazy_and_has_no_runtime_identity_before_iteration() -> None:
    woobe = Woobe(base_url="http://localhost:9999")
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    chat = agent.chat(input="Olá")

    assert chat.session_id is None
    assert chat.run_id is None
    assert chat.target_alias == "support"


@pytest.mark.asyncio
async def test_agent_validates_pydantic_output_context() -> None:
    transport = _ContractTransport()
    woobe = Woobe(base_url="http://unused")
    woobe._transport = transport  # type: ignore[assignment]
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    result = await agent.validate_output_context(SupportOutput)

    assert result.valid is True
    assert result.release_version == "v1.0.0"
    assert transport.calls == [
        {
            "key": "runtime-key",
            "output_context": {
                "properties": {
                    "message": {"title": "Message", "type": "string"},
                    "confidence": {"title": "Confidence", "type": "number"},
                },
                "required": ["message", "confidence"],
                "title": "SupportOutput",
                "type": "object",
            },
        }
    ]


@pytest.mark.asyncio
async def test_network_uses_same_output_context_validation_surface() -> None:
    transport = _ContractTransport()
    woobe = Woobe(base_url="http://unused")
    woobe._transport = transport  # type: ignore[assignment]
    network = woobe.connect.network(alias="support-network", key="network-key")

    result = await network.validate_output_context(
        {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }
    )

    assert result.valid is True
    assert transport.calls[0]["key"] == "network-key"
