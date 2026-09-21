from __future__ import annotations

import pytest
from pydantic import BaseModel

from woobe.contracts import output_context_schema


class Detail(BaseModel):
    flags: list[bool]


class SupportOutput(BaseModel):
    message: str
    detail: Detail


def test_output_context_schema_inlines_nested_pydantic_refs() -> None:
    schema = output_context_schema(SupportOutput)

    assert schema is not None
    assert "$defs" not in schema
    assert schema["properties"]["detail"] == {
        "properties": {
            "flags": {
                "items": {"type": "boolean"},
                "title": "Flags",
                "type": "array",
            }
        },
        "required": ["flags"],
        "title": "Detail",
        "type": "object",
    }


def test_output_context_schema_accepts_model_instance() -> None:
    schema = output_context_schema(
        SupportOutput(
            message="ok",
            detail=Detail(flags=[True]),
        )
    )

    assert schema is not None
    assert schema["properties"]["message"]["type"] == "string"


def test_output_context_schema_inlines_explicit_json_schema_refs() -> None:
    raw = {
        "$defs": {
            "Detail": {
                "type": "object",
                "properties": {"flag": {"type": "boolean"}},
                "required": ["flag"],
            }
        },
        "type": "object",
        "properties": {"detail": {"$ref": "#/$defs/Detail"}},
        "required": ["detail"],
    }

    assert output_context_schema(raw) == {
        "type": "object",
        "properties": {
            "detail": {
                "type": "object",
                "properties": {"flag": {"type": "boolean"}},
                "required": ["flag"],
            }
        },
        "required": ["detail"],
    }


def test_output_context_schema_keeps_explicit_dict() -> None:
    raw = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    assert output_context_schema(raw) == raw


def test_output_context_schema_rejects_unsupported_values() -> None:
    with pytest.raises(TypeError, match="output_context"):
        output_context_schema("message: str")  # type: ignore[arg-type]
