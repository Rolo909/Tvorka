"""Parse the proposed file changes from the coding model's answer."""

from __future__ import annotations

from dataclasses import dataclass

from tvorka.core.code.workspace import WorkspaceError


@dataclass(frozen=True)
class EditBlock:
    path: str
    search: str
    replace: str


def parse_blocks(text: str) -> list[EditBlock]:
    lines = text.splitlines(keepends=True)
    blocks = []
    path = ""
    search: list[str] = []
    replacement: list[str] = []
    state = "path"
    for number, line in enumerate(lines, start=1):
        marker = line.rstrip()
        if marker == "<<<<<<< SEARCH" and state == "path" and path:
            state = "search"
        elif marker == "=======" and state == "search":
            state = "replace"
        elif marker == ">>>>>>> REPLACE" and state == "replace":
            blocks.append(EditBlock(path, "".join(search), "".join(replacement)))
            search, replacement, path = [], [], ""
            state = "path"
        elif marker in ("<<<<<<< SEARCH", "=======", ">>>>>>> REPLACE"):
            raise WorkspaceError("bad_block", str(number))
        elif state == "search":
            search.append(line)
        elif state == "replace":
            replacement.append(line)
        elif line.strip() and not marker.startswith("```"):
            path = line.strip()
    if state != "path":
        raise WorkspaceError("bad_block", str(len(lines)))
    return blocks
