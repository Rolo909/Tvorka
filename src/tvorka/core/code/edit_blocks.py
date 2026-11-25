"""Parse the proposed file changes from the coding model's answer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from tvorka.core.code.workspace import WorkspaceError

_FENCE = re.compile(r"^```([^\r\n`]*)\r?\n(.*?)^```[ \t]*$", re.M | re.S)
_FILENAMES = {"python": "main.py", "py": "main.py", "html": "index.html", "css": "style.css",
              "js": "script.js", "javascript": "script.js", "typescript": "script.ts",
              "json": "data.json", "markdown": "README.md"}
_NAME = re.compile(r"(?:[\w.-]+/)*[\w-][\w.-]*\.[A-Za-z0-9]{1,12}")


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


def code_files(text: str) -> dict[str, str]:
    """Use ordinary HTML/CSS/JS names when a fenced example omits filenames."""
    files: dict[str, str] = {}
    used: set[str] = set()
    for index, (hint, content) in enumerate(_FENCE.findall(text), 1):
        words = hint.split()
        names = (word.removeprefix("filename=").strip("\"'") for word in words)
        filename = next((name for name in names if _NAME.fullmatch(name) and ".." not in name.split("/")), "")
        path = PurePosixPath(filename or _FILENAMES.get(words[0].lower() if words else "", "snippet.txt"))
        root = path
        while path.as_posix().casefold() in used:
            path = root.with_stem(f"{root.stem}-{index}")
            index += 1
        used.add(path.as_posix().casefold())
        files[path.as_posix()] = content
    return files
