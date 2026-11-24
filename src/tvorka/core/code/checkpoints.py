"""Keep undo records in the app's session storage, outside the working folder."""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

from tvorka.core.code.workspace import Change, Workspace, WorkspaceError


def _pack(data: bytes | None) -> str | None:
    return base64.b64encode(data).decode("ascii") if data is not None else None


def _unpack(data: str | None) -> bytes | None:
    return base64.b64decode(data, validate=True) if data is not None else None


class Checkpoints:
    def __init__(self, workspace: Workspace, folder: Path) -> None:
        self.workspace = workspace
        self.folder = folder.resolve()
        if self.folder.is_relative_to(workspace.root):
            raise WorkspaceError("outside", str(folder))

    def _records(self) -> list[Path]:
        return sorted((p for p in self.folder.glob("*.json") if p.stem.isdecimal()),
                      key=lambda p: int(p.stem))

    def apply(self, change: Change) -> int:
        replacement = change.replacement_bytes()
        records = self._records()
        number = int(records[-1].stem) + 1 if records else 1
        self.folder.mkdir(parents=True, exist_ok=True)
        file = self.folder / f"{number}.json"
        data = {"path": change.path, "before": _pack(change.before_bytes), "after": _pack(replacement)}
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.folder, delete=False) as handle:
            pending = Path(handle.name)
            try:
                json.dump(data, handle)
                handle.close()
                pending.replace(file)
            finally:
                pending.unlink(missing_ok=True)
        try:
            self.workspace.replace_bytes(change.path, change.before_bytes, replacement)
        except (WorkspaceError, OSError):
            file.unlink()
            raise
        return number

    def _undo(self, file: Path) -> None:
        data = json.loads(file.read_text(encoding="utf-8"))
        before, after = _unpack(data["before"]), _unpack(data["after"])
        # A restart can leave a checkpoint whose edit did not reach the workspace.
        if self.workspace.snapshot(data["path"]) != before:
            self.workspace.replace_bytes(data["path"], after, before)
        file.unlink()

    def undo_last(self) -> bool:
        records = self._records()
        if not records:
            return False
        self._undo(records[-1])
        return True

    def undo_to(self, number: int) -> None:
        for file in reversed(self._records()):
            if int(file.stem) <= number:
                break
            self._undo(file)
