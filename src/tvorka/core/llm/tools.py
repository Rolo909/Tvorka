"""OpenAI-compatible tool descriptions shared by the chat and coding flows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    required: tuple[str, ...] = ()

    def accepts(self, arguments: dict[str, Any] | None) -> bool:
        if arguments is None or not set(self.required).issubset(arguments):
            return False
        types = {"string": str, "integer": int, "boolean": bool}
        return all(key in self.properties and type(value) is types[self.properties[key]["type"]]
                   for key, value in arguments.items())


def openai_schema(tools: Iterable[Tool]) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {
        "name": tool.name, "description": tool.description,
        "parameters": {"type": "object", "properties": tool.properties,
                       "required": list(tool.required), "additionalProperties": False},
    }} for tool in tools]
