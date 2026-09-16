from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from woobe._transport.http import RuntimeTransport
from woobe._transport.sse import SseFrame
from woobe.errors import (
    WoobeConnectionError,
    WoobeProtocolError,
    WoobeRecoveryError,
    WoobeRequestError,
    WoobeStreamGapError,
)
from woobe.events import WoobeEvent

TargetKind = Literal["AGENT", "NETWORK"]
_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_TERMINAL_EVENT_TYPES = {
    "done",
    "error",
    "cancelled",
    "execution_completed",
    "execution_failed",
    "execution_cancelled",
    "execution_timed_out",
}
_IDENTITY_KEYS = {
    "type",
    "run_id",
    "execution_id",
    "session_id",
    "network_session_id",
    "sequence",
    "event_id",
    "occurred_at",
    "created_at",
    "scope_type",
    "scope_id",
}


@dataclass(slots=True)
class _PendingEvent:
    type: str
    sequence: int | None
    event_id: str | None
    occurred_at: Any
    scope_type: str | None
    scope_id: str | None
    payload: dict[str, Any]


class Chat:
    """Lazy runtime interaction.

    Constructing a Chat performs no HTTP request. The initial Runtime request starts
    only when ``events()`` is iterated.
    """

    def __init__(
        self,
        *,
        transport: RuntimeTransport,
        target_kind: TargetKind,
        target_alias: str,
        key: str,
        input: str,
        session_id: str | None,
        max_reconnect_attempts: int,
        reconnect_base_delay_seconds: float,
    ) -> None:
        self._transport = transport
        self._target_kind = target_kind
        self._target_alias = target_alias
        self._key = key
        self._input = input
        self._session_id = session_id
        self._run_id: str | None = None
        self._last_sequence: int | None = None
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_base_delay_seconds = reconnect_base_delay_seconds
        self._idempotency_key = str(uuid4())
        self._started = False

    @property
    def target_alias(self) -> str:
        return self._target_alias

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def run_id(self) -> str | None:
        return self._run_id

    async def events(self):
        """Execute lazily and yield normalized ``WoobeEvent`` objects.

        After a canonical Run ID is known, recovery always uses the reattach GET.
        The SDK never submits a second Agent POST merely to recover a broken stream.
        """

        if self._started:
            raise WoobeProtocolError("Chat.events() can only be consumed once")
        self._started = True

        mode: Literal["new", "reattach"] = "new"
        reconnect_attempt = 0
        pending: list[_PendingEvent] = []

        while True:
            try:
                source = (
                    self._transport.stream_new_run(
                        key=self._key,
                        message=self._input,
                        session_id=self._session_id,
                        idempotency_key=self._idempotency_key,
                    )
                    if mode == "new"
                    else self._transport.stream_run(key=self._key, run_id=self._require_run_id())
                )

                async for frame in source:
                    item = self._normalize(frame)
                    if not self._accept_sequence(item):
                        continue
                    pending.append(item)

                    if self._run_id is not None and self._session_id is not None:
                        for ready in pending:
                            yield self._to_event(ready)
                        pending.clear()

                    if self._is_terminal(item):
                        if pending:
                            raise WoobeProtocolError(
                                "Terminal Runtime state was received before run/session identity"
                            )
                        return

                raise WoobeConnectionError("Runtime stream ended before terminal state")

            except (WoobeConnectionError, WoobeStreamGapError) as exc:
                pending.clear()
                mode, reconnect_attempt = await self._recover(
                    mode=mode,
                    reconnect_attempt=reconnect_attempt,
                    cause=exc,
                )
            except WoobeRequestError as exc:
                if not exc.retryable:
                    raise
                pending.clear()
                mode, reconnect_attempt = await self._recover(
                    mode=mode,
                    reconnect_attempt=reconnect_attempt,
                    cause=exc,
                )

    async def _recover(
        self,
        *,
        mode: Literal["new", "reattach"],
        reconnect_attempt: int,
        cause: Exception,
    ) -> tuple[Literal["new", "reattach"], int]:
        if self._run_id is None and self._session_id is not None:
            self._run_id = await self._transport.resolve_active_run(
                key=self._key,
                session_id=self._session_id,
            )

        if self._run_id is None:
            if self._target_kind == "NETWORK" and mode == "new":
                if reconnect_attempt >= self._max_reconnect_attempts:
                    raise WoobeRecoveryError(
                        "Network Run could not be recovered before its canonical ID was observed"
                    ) from cause
                await self._wait(reconnect_attempt)
                return "new", reconnect_attempt + 1

            raise WoobeRecoveryError(
                "Runtime connection failed before the canonical Run could be recovered; "
                "the SDK will not submit another Agent execution because that could duplicate the Run"
            ) from cause

        if reconnect_attempt >= self._max_reconnect_attempts:
            raise WoobeRecoveryError(
                f"Run {self._run_id} exceeded the reattach retry budget"
            ) from cause

        await self._wait(reconnect_attempt)
        return "reattach", reconnect_attempt + 1

    async def _wait(self, reconnect_attempt: int) -> None:
        delay = self._reconnect_base_delay_seconds * (reconnect_attempt + 1)
        if delay > 0:
            await asyncio.sleep(delay)

    def _normalize(self, frame: SseFrame) -> _PendingEvent:
        raw = dict(frame.data)
        nested = raw.get("data")
        is_network_envelope = isinstance(nested, dict) and (
            "execution_id" in raw or "protocol_version" in raw
        )
        source = dict(nested) if is_network_envelope else raw

        run_id = self._first_text(
            raw.get("run_id"),
            raw.get("execution_id"),
            source.get("run_id"),
            source.get("execution_id"),
        )
        if run_id is not None:
            if self._run_id is not None and self._run_id != run_id:
                raise WoobeProtocolError(
                    f"Runtime stream changed Run identity from {self._run_id} to {run_id}"
                )
            self._run_id = run_id

        session_id = self._first_text(
            raw.get("session_id"),
            raw.get("network_session_id"),
            source.get("session_id"),
            source.get("network_session_id"),
        )
        if session_id is not None:
            if self._session_id is not None and self._session_id != session_id:
                raise WoobeProtocolError(
                    "Runtime stream returned a Session different from the requested Session"
                )
            self._session_id = session_id

        sequence = self._sequence_of(raw, source, frame.event_id)
        event_id = self._first_text(raw.get("event_id"), source.get("event_id"))
        occurred_at = (
            raw.get("occurred_at")
            or raw.get("created_at")
            or source.get("occurred_at")
            or source.get("created_at")
        )
        scope_type = self._first_text(raw.get("scope_type"), source.get("scope_type"))
        scope_id = self._first_text(raw.get("scope_id"), source.get("scope_id"))

        payload = {key: value for key, value in source.items() if key not in _IDENTITY_KEYS}
        return _PendingEvent(
            type=frame.event,
            sequence=sequence,
            event_id=event_id,
            occurred_at=occurred_at,
            scope_type=scope_type,
            scope_id=scope_id,
            payload=payload,
        )

    def _accept_sequence(self, item: _PendingEvent) -> bool:
        sequence = item.sequence
        if sequence is None:
            return True

        if item.type == "run.state":
            if item.payload.get("realtime_available") is False:
                return True
            if self._last_sequence is not None and sequence < self._last_sequence:
                return False
            self._last_sequence = sequence
            return True

        if self._last_sequence is not None:
            if sequence <= self._last_sequence:
                return False
            expected = self._last_sequence + 1
            if sequence != expected:
                raise WoobeStreamGapError(
                    f"Runtime event sequence gap: expected {expected}, received {sequence}"
                )
        self._last_sequence = sequence
        return True

    def _to_event(self, item: _PendingEvent) -> WoobeEvent:
        run_id = self._require_run_id()
        session_id = self._session_id
        if session_id is None:
            raise WoobeProtocolError("Runtime event does not have a Session identity")

        occurred_at = item.occurred_at
        if isinstance(occurred_at, datetime):
            parsed_occurred_at = occurred_at
        elif isinstance(occurred_at, str) and occurred_at:
            try:
                parsed_occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            except ValueError:
                parsed_occurred_at = None
        else:
            parsed_occurred_at = None

        return WoobeEvent(
            event_id=item.event_id,
            session_id=session_id,
            run_id=run_id,
            run_kind=self._target_kind,
            sequence=item.sequence,
            type=item.type,
            occurred_at=parsed_occurred_at,
            scope_type=item.scope_type,
            scope_id=item.scope_id,
            payload=item.payload,
        )

    @staticmethod
    def _is_terminal(item: _PendingEvent) -> bool:
        if item.type in _TERMINAL_EVENT_TYPES:
            return True
        if item.type != "run.state":
            return False
        status = item.payload.get("status")
        return isinstance(status, str) and status.lower() in _TERMINAL_STATUSES

    def _require_run_id(self) -> str:
        if self._run_id is None:
            raise WoobeProtocolError("Canonical Run ID is not available")
        return self._run_id

    @staticmethod
    def _first_text(*values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    @staticmethod
    def _sequence_of(
        raw: dict[str, Any],
        source: dict[str, Any],
        event_id: str | None,
    ) -> int | None:
        candidates = (raw.get("sequence"), source.get("sequence"), event_id)
        for value in candidates:
            if isinstance(value, bool) or value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None
