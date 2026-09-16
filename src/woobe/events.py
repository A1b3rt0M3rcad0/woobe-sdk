from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RunKind = Literal["AGENT", "NETWORK"]


class WoobeEvent(BaseModel):
    """Canonical event exposed by the Python SDK.

    ``run_id`` and ``session_id`` are required for every event yielded to user code.
    The SDK never fabricates runtime event types or payload semantics.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str | None = None
    session_id: str
    run_id: str
    run_kind: RunKind
    sequence: int | None = None
    type: str
    occurred_at: datetime | None = None
    scope_type: str | None = None
    scope_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
