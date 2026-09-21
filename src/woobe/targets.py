from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError as PydanticValidationError

from woobe.chat import Chat
from woobe.contracts import (
    OutputContextInput,
    OutputContextValidation,
    output_context_schema,
)
from woobe.errors import WoobeProtocolError

if TYPE_CHECKING:
    from woobe.client import Woobe

TargetKind = Literal["AGENT", "NETWORK"]


class _RuntimeTarget:
    def __init__(self, *, client: Woobe, alias: str, key: str, kind: TargetKind) -> None:
        if not alias.strip():
            raise ValueError("alias must not be empty")
        if not key.strip():
            raise ValueError("key must not be empty")
        self._client = client
        self._alias = alias.strip()
        self._key = key.strip()
        self._kind = kind

    @property
    def alias(self) -> str:
        return self._alias

    async def validate_output_context(
        self,
        output_context: OutputContextInput,
    ) -> OutputContextValidation:
        data = await self._client._transport.validate_output_context(
            key=self._key,
            output_context=output_context_schema(output_context),
        )
        try:
            return OutputContextValidation.model_validate(data)
        except PydanticValidationError as exc:
            raise WoobeProtocolError(
                "Output Context validation response has an invalid data envelope"
            ) from exc

    def chat(
        self,
        *,
        input: str,
        session_id: str | None = None,
        external_context: dict[str, Any] | None = None,
    ) -> Chat:
        if not input.strip():
            raise ValueError("input must not be empty")
        return Chat(
            transport=self._client._transport,
            target_kind=self._kind,
            target_alias=self._alias,
            key=self._key,
            input=input,
            session_id=session_id,
            external_context=external_context,
            max_reconnect_attempts=self._client._max_reconnect_attempts,
            reconnect_base_delay_seconds=self._client._reconnect_base_delay_seconds,
        )


class Agent(_RuntimeTarget):
    def __init__(self, *, client: Woobe, alias: str, key: str) -> None:
        super().__init__(client=client, alias=alias, key=key, kind="AGENT")


class Network(_RuntimeTarget):
    def __init__(self, *, client: Woobe, alias: str, key: str) -> None:
        super().__init__(client=client, alias=alias, key=key, kind="NETWORK")
