"""The structured screenplay shared by the planner, editor and generation queue."""

from __future__ import annotations

import json
from dataclasses import dataclass

from tvorka.core.llm.prompts import STYLE_HINTS, Task

MAX_SCENES = 6


@dataclass(frozen=True)
class Scene:
    image: str
    motion: str
    narration: str


FIELDS = tuple(Scene.__dataclass_fields__)


def plan(idea: str, count: int, language: str, image_style: str) -> Task:
    if not 1 <= count <= MAX_SCENES:
        raise ValueError("Invalid scene count")
    schema = {
        "type": "object", "required": ["scenes"], "additionalProperties": False,
        "properties": {"scenes": {
            "type": "array", "minItems": count, "maxItems": count,
            "items": {"type": "object", "required": list(FIELDS), "additionalProperties": False,
                      "properties": {field: {"type": "string"} for field in FIELDS}},
        }},
    }
    instruction = (f"Turn the user's idea into exactly {count} consecutive scenes for a short video. "
                   f"For each scene write image as {STYLE_HINTS[image_style]}. "
                   "Repeat essential subject and style details in each image prompt for continuity. "
                   "Write motion in English as two short sentences animating that image in one shot. "
                   f"Write narration as a short voice-over sentence in the language with code {language}. "
                   "Return only a JSON object with a scenes array. Every field must be non-empty.")
    return Task([{"role": "system", "content": instruction}, {"role": "user", "content": idea}],
                240 * count + 64, {"type": "json_object", "schema": schema})


def parse(answer: str, count: int) -> list[Scene]:
    """Reject partial or malformed output even when the local server enforces the schema."""
    data = json.loads(answer)
    rows = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != count or not 1 <= count <= MAX_SCENES:
        raise ValueError("Invalid scene count")
    scenes = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != set(FIELDS)
                or any(not isinstance(value, str) or not value.strip() for value in row.values())):
            raise ValueError("Invalid scene")
        scenes.append(Scene(**{field: row[field].strip() for field in FIELDS}))
    return scenes
