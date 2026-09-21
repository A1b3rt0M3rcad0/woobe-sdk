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
        return _inline_local_refs(type(output_context).model_json_schema())
    if isinstance(output_context, type) and issubclass(output_context, BaseModel):
        return _inline_local_refs(output_context.model_json_schema())
    raise TypeError(
        "output_context must be a Pydantic BaseModel type, BaseModel instance, dict, or None"
    )


def _inline_local_refs(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        definitions = schema.get("definitions")
    if not isinstance(definitions, dict):
        return schema

    def resolve(value: Any, stack: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [resolve(item, stack) for item in value]
        if not isinstance(value, dict):
            return value

        ref = value.get("$ref")
        if isinstance(ref, str):
            name = _local_ref_name(ref)
            if name is not None and name in definitions and name not in stack:
                target = resolve(definitions[name], (*stack, name))
                if isinstance(target, dict):
                    extras = {
                        key: resolve(child, stack)
                        for key, child in value.items()
                        if key != "$ref"
                    }
                    return {**target, **extras}

        return {
            key: resolve(child, stack)
            for key, child in value.items()
            if key not in {"$defs", "definitions"}
        }

    resolved = resolve(schema)
    return resolved if isinstance(resolved, dict) else schema


def _local_ref_name(ref: str) -> str | None:
    for prefix in ("#/$defs/", "#/definitions/"):
        if ref.startswith(prefix):
            return ref.removeprefix(prefix).replace("~1", "/").replace("~0", "~")
    return None
