from __future__ import annotations

from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict


OutputContextInput: TypeAlias = (
    dict[str, Any] | type[BaseModel] | BaseModel | None
)


class OutputContextIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class OutputContextValidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    valid: bool
    target_type: Literal["agent", "network"]
    target_id: str
    environment: str
    release_id: str
    release_version: str
    expected_output_context: dict[str, Any] | None
    received_output_context: dict[str, Any] | None
    expected_hash: str
    received_hash: str
    issues: list[OutputContextIssue]


def output_context_schema(output_context: OutputContextInput) -> dict[str, Any] | None:
    if output_context is None:
        return None
    if isinstance(output_context, dict):
        return dict(output_context)
    if isinstance(output_context, BaseModel):
        return type(output_context).model_json_schema()
    if isinstance(output_context, type) and issubclass(output_context, BaseModel):
        return output_context.model_json_schema()
    raise TypeError(
        "output_context must be a Pydantic BaseModel type, BaseModel instance, dict, or None"
    )
