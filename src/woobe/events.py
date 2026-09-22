from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RUNTIME_STREAM_PROTOCOL_VERSION = 2
RunKind = Literal["AGENT", "NETWORK"]


class AssistantMessage(BaseModel):
    """Typed payload for a public intermediate Assistant message."""

    model_config = ConfigDict(frozen=True, extra="allow")

    message_id: str = Field(min_length=1)
    content: str
    phase: str | None = None
    output_mode: Literal["intermediate"]
    provider: str | None = None
    model: str | None = None
    partial: bool | None = None
    status: str | None = None


class WoobeEvent(BaseModel):
    """Canonical semantic event emitted by the Woobe Runtime stream protocol v2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: Literal[2] = RUNTIME_STREAM_PROTOCOL_VERSION
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    run_kind: RunKind
    sequence: int = Field(ge=0, strict=True)
    type: str = Field(min_length=1)
    occurred_at: datetime
    payload: dict[str, Any]

    @property
    def assistant_message(self) -> AssistantMessage | None:
        """Return a typed intermediate Assistant message when this event carries one."""

        if self.type not in {
            "assistant_message_delta",
            "assistant_message_completed",
        }:
            return None
        return AssistantMessage.model_validate(self.payload)
