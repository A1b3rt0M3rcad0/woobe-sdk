from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from woobe.errors import WoobeProtocolError


@dataclass(frozen=True, slots=True)
class SseFrame:
    event: str
    data: dict[str, Any]
    event_id: str | None = None


class SseDecoder:
    """Small SSE decoder for the subset used by the Woobe Runtime API."""

    def __init__(self) -> None:
        self._event: str | None = None
        self._event_id: str | None = None
        self._data: list[str] = []

    def feed_line(self, line: str) -> SseFrame | None:
        if line == "":
            return self._flush()
        if line.startswith(":"):
            return None

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]

        if field == "event":
            self._event = value
        elif field == "id":
            self._event_id = value
        elif field == "data":
            self._data.append(value)
        return None

    def finish(self) -> SseFrame | None:
        return self._flush()

    def _flush(self) -> SseFrame | None:
        if not self._data:
            self._reset()
            return None

        raw_data = "\n".join(self._data)
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as exc:
            self._reset()
            raise WoobeProtocolError("Runtime SSE frame contains invalid JSON") from exc

        event = self._event
        event_id = self._event_id
        self._reset()

        if not isinstance(data, dict):
            raise WoobeProtocolError("Runtime SSE data must be a JSON object")
        if not event:
            candidate = data.get("type")
            event = candidate if isinstance(candidate, str) and candidate else "message"
        return SseFrame(event=event, data=data, event_id=event_id)

    def _reset(self) -> None:
        self._event = None
        self._event_id = None
        self._data = []
