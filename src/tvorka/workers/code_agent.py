"""Run code sessions off the UI thread through the shared local chat worker."""

from __future__ import annotations

import itertools
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal

from tvorka.core.catalog import ModelSpec
from tvorka.core.code.agent import AgentLoop, Decision, Event, Permissions, Reply, Stopped
from tvorka.core.code.sessions import SessionStore
from tvorka.core.code.tools import Approval
from tvorka.core.code.workspace import MAX_FILE_BYTES, Workspace, WorkspaceError
from tvorka.core.jobs import Job
from tvorka.core.llm.client import LlmError
from tvorka.workers.chat import NO_THINKING, ChatWorker, Launch
from tvorka.workers.generation import GenerationWorker

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Request:
    workspace: Workspace
    launch: Launch
    task: str
    mode: str
    selected: tuple[str, ...] = ()
    tools: bool = False
    image: ModelSpec | None = None


class CodeWorker(QThread):
    event_added = Signal(object)
    delta = Signal(str, str)
    approval_needed = Signal(int, object)
    settled = Signal(str)
    failed = Signal(str, str)

    def __init__(self, chat: ChatWorker, generation: GenerationWorker, store: SessionStore) -> None:
        super().__init__()
        self.chat, self.generation, self.store = chat, generation, store
        self.request: Request | None = None
        self.events: list[Event] = []
        self.partial = ""
        self.pending: tuple[int, Approval] | None = None
        self._decision: Decision | None = None
        self._permissions: dict[str, Permissions] = {}
        self._ids = itertools.count(1)
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self._resolved = threading.Event()
        self._llm_done = threading.Event()
        self._llm_id = 0
        self._llm_result: dict[str, Any] = {}
        self._llm_error: LlmError | None = None
        self._parts: list[str] = []
        self._live = False
        self._image_done = threading.Event()
        self._image_id = 0
        self._image_path = ""
        self._image_error: WorkspaceError | None = None
        direct = Qt.ConnectionType.DirectConnection
        chat.delta.connect(self._on_delta, direct)
        chat.finished.connect(self._on_reply, direct)
        chat.failed.connect(self._on_llm_error, direct)
        chat.cancelled.connect(self._on_llm_cancel, direct)
        generation.job_finished.connect(self._on_image, direct)
        generation.job_failed.connect(self._on_image_error, direct)
        generation.job_cancelled.connect(self._on_image_cancel, direct)

    def submit(self, request: Request) -> bool:
        if self.isRunning():
            return False
        self.events, self.partial, self.pending = [], "", None
        self._cancelled.clear()
        self.request = request
        self.start()
        return True

    def permissions(self, workspace: Workspace) -> Permissions:
        return self._permissions.setdefault(self.store.key(workspace), Permissions())

    def resolve(self, approval_id: int, action: str, note: str = "") -> None:
        with self._lock:
            if self.pending is None or self.pending[0] != approval_id or self._decision is not None:
                return
            approval = self.pending[1]
            allowed = {"apply", "reject"}
            if approval.allow_session:
                allowed.add("allow_session" if approval.kind == "command" else "apply_all_session")
            if action in allowed:
                self._decision = Decision(action, note[:2000])
                self.pending = None
                self._resolved.set()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled.set()
            self._resolved.set()
            if self._llm_id:
                self.chat.cancel(self._llm_id)
                self._llm_id = 0
                self._llm_done.set()
            if self._image_id:
                self.generation.cancel(self._image_id)

    def _check(self) -> None:
        if self._cancelled.is_set():
            raise Stopped

    def _approve(self, approval: Approval) -> Decision:
        with self._lock:
            self._check()
            identifier = next(self._ids)
            self.pending = (identifier, approval)
            self._decision = None
            self._resolved.clear()
        self.approval_needed.emit(identifier, approval)
        self._resolved.wait()
        self._check()
        assert self._decision is not None
        return self._decision

    def _emit_event(self, event: Event) -> None:
        with self._lock:
            if event.kind == "assistant":
                self.partial = ""
            self.events.append(event)
        self.event_added.emit(event)

    def _complete(self, messages: list[dict[str, Any]], params: dict[str, Any], live: bool) -> Reply:
        assert self.request is not None
        with self._lock:
            self._check()
            self._parts = []
            self._live = live
            self._llm_error = None
            self._llm_result = {}
            self._llm_done.clear()
            self._llm_id = self.chat.submit(self.request.launch, list(messages), {**params, **NO_THINKING})
        self._llm_done.wait()
        self._check()
        if self._llm_error is not None:
            raise self._llm_error
        return Reply("".join(self._parts), self._llm_result.get("message_calls", []), self._llm_result)

    def _on_delta(self, request_id: int, text: str, reasoning: str) -> None:
        with self._lock:
            if request_id != self._llm_id:
                return
            self._parts.append(text)
            if self._live:
                self.partial += text
                self.delta.emit(text, reasoning)

    def _on_reply(self, request_id: int, stats: dict[str, Any]) -> None:
        with self._lock:
            if request_id == self._llm_id:
                self._llm_result = stats
                self._llm_id = 0
                self._llm_done.set()

    def _on_llm_error(self, request_id: int, code: str, detail: str) -> None:
        with self._lock:
            if request_id == self._llm_id:
                self._llm_error = LlmError(code, detail)
                self._llm_id = 0
                self._llm_done.set()

    def _on_llm_cancel(self, request_id: int) -> None:
        self._on_llm_error(request_id, "cancelled", "")

    def _generate_image(self, prompt: str, width: int, height: int) -> bytes:
        assert self.request is not None and self.request.image is not None
        spec = self.request.image
        with TemporaryDirectory(prefix="tvorka-code-image-") as folder:
            job = Job("image", spec.id, prompt, {"width": width, "height": height, "count": 1,
                                                 "format": "png", "preview": True,
                                                 "guidance": spec.default("guidance", 0.0)},
                      preview_dir=Path(folder))
            with self._lock:
                self._check()
                self._image_done.clear()
                self._image_path, self._image_error = "", None
                self._image_id = self.generation.submit(job)
            self._image_done.wait()
            self._check()
            if self._image_error is not None:
                raise self._image_error
            image_path = Path(self._image_path).resolve()
            if not image_path.is_relative_to(Path(folder).resolve()):
                raise WorkspaceError("outside", self._image_path)
            with image_path.open("rb") as file:
                data = file.read(MAX_FILE_BYTES + 1)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise WorkspaceError("image_format", image_path.name)
            return data

    def _on_image(self, job_id: int, results: list[dict[str, Any]]) -> None:
        with self._lock:
            if job_id == self._image_id:
                self._image_id = 0
                if results:
                    self._image_path = results[0]["path"]
                else:
                    self._image_error = WorkspaceError("failed", "No image was returned")
                self._image_done.set()

    def _on_image_error(self, job_id: int, code: str, detail: str) -> None:
        with self._lock:
            if job_id == self._image_id:
                self._image_id = 0
                self._image_error = WorkspaceError(code, detail)
                self._image_done.set()

    def _on_image_cancel(self, job_id: int) -> None:
        self._on_image_error(job_id, "cancelled", "")

    def run(self) -> None:
        request = self.request
        assert request is not None
        status = "failed"
        try:
            session = self.store.load(request.workspace)
            if session.mode != request.mode:
                session.messages = [{"role": m["role"], "content": m["content"]} for m in session.messages
                                    if m["role"] in {"user", "assistant"} and m.get("content")]
            session.mode, session.model_id = request.mode, request.launch.model_id
            session.ctx = request.launch.plan.ctx
            image = self._generate_image if request.image else None
            loop = AgentLoop(request.workspace, self.store.checkpoints(request.workspace), session,
                             self._complete, self._approve, self._emit_event, self._check,
                             self.permissions(request.workspace), image)
            try:
                status = loop.run(request.task, request.selected, request.tools)
            finally:
                self.store.save(request.workspace, session)
        except Stopped:
            status = "cancelled"
        except (LlmError, WorkspaceError) as exc:
            self.failed.emit(exc.code, exc.detail)
        except Exception as exc:
            log.exception("code session failed")
            self.failed.emit("failed", str(exc))
        finally:
            with self._lock:
                self.pending = None
                self.partial = ""
            self.settled.emit(status)
