"""The chat model as a helper for the other sections: one request, one answer, no conversation.

The request goes through the same ``ChatWorker`` (and the same video memory arbiter) as the chat;
the chat page ignores answers to requests it did not make.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject

from tvorka.core.catalog import ModelSpec
from tvorka.core.llm.prompts import Task
from tvorka.workers.chat import NO_THINKING

ORDER = ["great", "good", "slow", "very_slow", "no"]


class Assistant(QObject):
    def __init__(self, services: Any) -> None:
        super().__init__()
        self.services = services
        self._pending: dict[int, tuple[list[str], Callable[[str], None], Callable[[str], None]]] = {}
        worker = services.chat_worker
        worker.delta.connect(self._on_delta)
        worker.finished.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(lambda request_id: self._on_failed(request_id, "cancelled", ""))

    def model(self, vision: bool = False) -> ModelSpec | None:
        """The chat model to ask: the one chosen in the Chat section if it is ready, else the best one."""
        services = self.services
        engine = services.chat_runtime()
        if engine is None or not services.installed(engine):
            return None
        chosen = services.catalog.get(services.settings.recall("chat", "model", "") or "")
        candidates = ([chosen] if chosen else []) + services.catalog.all("chat")
        best: tuple[int, int, float] | None = None
        pick = None
        for spec in candidates:
            if not services.installed(spec) or (vision and services.store.chat_files(spec)[1] is None):
                continue
            fit = services.fit(spec)
            if fit is None or fit.verdict == "no":
                continue
            rank = (0 if spec is chosen else 1, ORDER.index(fit.verdict), spec.download_gb)
            if best is None or rank < best:
                best, pick = rank, spec
        return pick

    def ask(self, task: Task, on_done: Callable[[str], None], on_failed: Callable[[str], None],
            vision: bool = False) -> int:
        """Send ``task``; the answer (or an error code) comes to the callbacks. 0 when it cannot be sent:
        ``no_chat_model`` / ``no_vision`` are then reported right away."""
        spec = self.model(vision)
        launch = self.services.chat_launch(spec) if spec is not None else None
        if launch is None:
            on_failed("no_vision" if vision and self.model() is not None else "no_chat_model")
            return 0
        params = {"max_tokens": task.max_tokens, "temperature": 0.3, **NO_THINKING}
        request = self.services.chat_worker.submit(launch, task.messages, params)
        self._pending[request] = ([], on_done, on_failed)
        return request

    def cancel(self, request: int) -> None:
        if self._pending.pop(request, None) is not None:
            self.services.chat_worker.cancel(request)

    def _on_delta(self, request: int, text: str, _reasoning: str) -> None:
        if request in self._pending:
            self._pending[request][0].append(text)

    def _on_finished(self, request: int, _stats: dict) -> None:
        parts, on_done, _failed = self._pending.pop(request, (None, None, None))
        if on_done is not None:
            on_done("".join(parts))

    def _on_failed(self, request: int, code: str, _detail: str) -> None:
        _parts, _done, on_failed = self._pending.pop(request, (None, None, None))
        if on_failed is not None:
            on_failed(code)
