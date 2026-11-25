"""Persist a project's conversation and undo records in Tvorka's data directory."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from tvorka.core.code.checkpoints import Checkpoints
from tvorka.core.code.workspace import Workspace, WorkspaceError


@dataclass
class Session:
    id: str
    title: str
    workspace: str
    model_id: str = ""
    mode: str = "edit"
    ctx: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    updated: float = 0


class SessionStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    @staticmethod
    def key(workspace: Workspace) -> str:
        return hashlib.sha256(os.fsencode(os.path.normcase(str(workspace.root)))).hexdigest()

    def load(self, workspace: Workspace) -> Session:
        key = self.key(workspace)
        try:
            data = json.loads((self.folder / f"{key}.json").read_text(encoding="utf-8"))
            session = Session(**data)
            if session.id != key or Path(session.workspace) != workspace.root:
                raise ValueError("Session project does not match")
            return session
        except FileNotFoundError:
            return Session(key, workspace.root.name, str(workspace.root))
        except (ValueError, TypeError) as exc:
            raise WorkspaceError("invalid_session", str(workspace.root)) from exc

    def save(self, workspace: Workspace, session: Session) -> None:
        self._check_folder(workspace)
        session.updated = time.time()
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self.folder / f"{self.key(workspace)}.json"
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.folder, delete=False) as file:
            staging = Path(file.name)
            try:
                json.dump(asdict(session), file, ensure_ascii=False)
                file.close()
                staging.replace(target)
            finally:
                staging.unlink(missing_ok=True)

    def checkpoints(self, workspace: Workspace) -> Checkpoints:
        self._check_folder(workspace)
        return Checkpoints(workspace, self.folder / self.key(workspace) / "checkpoints")

    def _check_folder(self, workspace: Workspace) -> None:
        if self.folder.resolve().is_relative_to(workspace.root):
            raise WorkspaceError("outside", str(self.folder))
