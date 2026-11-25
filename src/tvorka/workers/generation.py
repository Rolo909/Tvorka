"""Generation thread: one job at a time, the model stays loaded between jobs."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtCore import QThread, Signal

from tvorka.core import advisor
from tvorka.core.advisor import Plan
from tvorka.core.catalog import Catalog
from tvorka.core.hardware import Hardware
from tvorka.core.jobs import History, Job, Result, output_file
from tvorka.core.memory import VideoMemory
from tvorka.core.settings import Settings
from tvorka.core.store import ModelStore
from tvorka.core.storyboard import Scene
from tvorka.engines import media
from tvorka.engines.base import (
    Cancelled,
    Context,
    Engine,
    EngineError,
    create_engine,
    free_memory,
    is_oom,
)

log = logging.getLogger(__name__)

_UNLOAD = object()


class GenerationWorker(QThread):
    """Owns the loaded engine. All heavy imports (torch, diffusers) happen here."""

    job_started = Signal(int)
    job_progress = Signal(int, float, str)  # id, fraction, stage code
    job_finished = Signal(int, list)  # id, [Result as dict]
    job_failed = Signal(int, str, str)  # id, error code, detail
    job_cancelled = Signal(int)
    model_changed = Signal(str)  # id of the model held in memory, "" when none
    queue_changed = Signal(int)  # jobs waiting or running

    def __init__(self, settings: Settings, catalog: Catalog, store: ModelStore,
                 history: History) -> None:
        super().__init__()
        self._settings = settings
        self._catalog = catalog
        self._store = store
        self._history = history
        self._queue: queue.Queue[Any] = queue.Queue()
        self._cancel: set[int] = set()
        self._lock = threading.Lock()
        self._jobs: set[int] = set()  # submitted and not finished yet
        self._engine: Engine | None = None
        self._hardware: Hardware | None = None
        self._stopping = False
        self._busy = threading.RLock()  # held while the engine is used; the arbiter waits on it
        self._memory: VideoMemory | None = None
        self.current_job: int | None = None

    # --- called from the GUI thread ------------------------------------
    def set_hardware(self, hardware: Hardware) -> None:
        self._hardware = hardware

    def attach_memory(self, memory: VideoMemory) -> None:
        """Share the graphics card with the chat server through ``memory``."""
        self._memory = memory
        memory.register("generation", self._release)

    def _release(self, cancelled: Callable[[], bool]) -> bool:
        """Called from another thread: unload the model once the current job is done."""
        while not self._busy.acquire(timeout=0.2):
            if cancelled():
                return False
        try:
            self._drop_engine()
        finally:
            self._busy.release()
        return True

    def submit(self, job: Job) -> int:
        with self._lock:
            self._jobs.add(job.id)
            pending = len(self._jobs)
        self._queue.put(job)
        self.queue_changed.emit(pending)
        return job.id

    def cancel(self, job_id: int | None = None) -> None:
        """Cancel one job, or everything queued and running when ``job_id`` is None.

        Cancelling everything marks the jobs known right now, so a job submitted
        immediately afterwards still runs.
        """
        with self._lock:
            if job_id is None:
                self._cancel |= self._jobs
            elif job_id in self._jobs:
                self._cancel.add(job_id)

    def unload_model(self) -> None:
        self._queue.put(_UNLOAD)

    def shutdown(self) -> None:
        self._stopping = True
        self.cancel(None)
        self._queue.put(None)
        self.wait(15000)

    @property
    def loaded_model(self) -> str:
        return self._engine.spec.id if self._engine else ""

    # --- worker thread -------------------------------------------------
    def _is_cancelled(self, job_id: int) -> bool:
        with self._lock:
            return self._stopping or job_id in self._cancel

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            if item is _UNLOAD:
                self._drop_engine()
                continue
            job: Job = item
            self.current_job = job.id
            try:
                self._run_job(job)
            finally:
                self.current_job = None
                with self._lock:
                    self._jobs.discard(job.id)
                    self._cancel.discard(job.id)
                    pending = len(self._jobs)
                self.queue_changed.emit(pending)
        self._drop_engine()

    def _run_job(self, job: Job) -> None:
        if self._is_cancelled(job.id):
            self.job_cancelled.emit(job.id)
            return
        self.job_started.emit(job.id)
        settings = (replace(self._settings, output_dir=str(job.preview_dir))
                    if job.preview_dir is not None and job.get("preview") else self._settings)
        ctx = Context(
            settings, self._store,
            lambda fraction, stage: self.job_progress.emit(job.id, fraction, stage),
            lambda: self._is_cancelled(job.id),
        )
        try:
            results = self._storyboard(job, ctx) if job.get("storyboard") else self._generate(job, ctx)
            if not job.get("preview"):  # voice samples and other previews stay out of the gallery
                for result in results:
                    self._history.add(result)
            self.job_finished.emit(job.id, [asdict(r) for r in results])
        except Cancelled:
            self.job_cancelled.emit(job.id)
        except EngineError as exc:
            log.warning("job %s failed: %s %s", job.id, exc.code, exc.detail)
            self.job_failed.emit(job.id, exc.code, exc.detail)
        except Exception as exc:
            log.exception("job %s crashed", job.id)
            if is_oom(exc):
                self._drop_engine()
                self.job_failed.emit(job.id, "out_of_memory", "")
            else:
                self.job_failed.emit(job.id, "failed", f"{exc.__class__.__name__}: {exc}"[:800])
        finally:
            if not self._settings.keep_model_loaded:
                self._drop_engine()

    def _generate(self, job: Job, ctx: Context) -> list[Result]:
        ctx.check()
        spec = self._catalog.get(job.model_id)
        if spec is None:
            raise EngineError("model_missing", job.model_id)
        plan, vram_gb = self._plan(spec, job)
        if self._memory is not None and not self._memory.claim(
                "generation", spec.id, vram_gb, lambda: ctx.cancelled):
            raise Cancelled
        with self._busy:
            return self._attempt(spec, plan, job, ctx)

    def _storyboard(self, job: Job, ctx: Context) -> list[Result]:
        started = time.perf_counter()
        scenes = [Scene(**row) for row in job.get("storyboard")]
        video = self._catalog.get(job.model_id)
        if video is None:
            raise EngineError("model_missing", job.model_id)
        if "i2v" not in video.reference:
            raise EngineError("reference_unsupported", video.name)
        image_model = self._catalog.get(job.get("image_model"))
        speech_model = self._catalog.get(job.get("speech_model"))
        if image_model is None or speech_model is None:
            raise EngineError("model_missing")
        if any(spec.source == "online" for spec in (image_model, video, speech_model)):
            raise EngineError("unsupported")
        width, height = (side // 2 * 2 for side in video.native)
        total_steps = len(scenes) * 3 + 1
        step = 0
        root = ctx.settings.output_path()
        root.mkdir(parents=True, exist_ok=True)
        # All media stay on the same volume as the final MP4 for atomic publication.
        with TemporaryDirectory(prefix=".tvorka-storyboard-", dir=root) as temporary:
            folder = Path(temporary)
            settings = replace(ctx.settings, output_dir=temporary)

            def generate(part: Job) -> Path:
                nonlocal step
                part.params["preview"] = True
                local = Context(settings, ctx.store,
                                lambda fraction, stage: ctx.progress((step + fraction) / total_steps, stage),
                                lambda: ctx.cancelled)
                [result] = self._generate(part, local)
                step += 1
                return Path(result.path)

            images = [generate(Job("image", image_model.id, scene.image, {
                "format": "png", "count": 1, "guidance": image_model.default("guidance", 0.0),
            })) for scene in scenes]
            videos = [generate(Job("video", video.id, scene.motion, {
                "format": "mp4", "width": width, "height": height, "reference": str(image),
                "reference_mode": "i2v", "guidance": video.default("guidance", 5.0),
            })) for scene, image in zip(scenes, images, strict=True)]
            voice = next((entry["id"] for entry in speech_model.voices
                          if entry["id"].startswith(f"v2/{job.get('narration_language')}_")), None)
            speech_params = {"format": "wav", "voice": voice}
            voices = [generate(Job("speech", speech_model.id, scene.narration, dict(speech_params)))
                      for scene in scenes]
            ctx.progress(step / total_steps, "encode")
            movie, poster = folder / "movie.mp4", folder / "poster.jpg"
            clips = list(zip(videos, voices, strict=True))
            duration = media.join_scenes(clips, movie, width, height, ctx.check)
            thumbnail = media.video_frame(videos[0], 0)
            thumbnail.thumbnail((640, 640))
            thumbnail.save(poster, quality=85)
            ctx.check()
            target = output_file(root, "video", "mp4")
            thumb = target.with_suffix(".jpg")
            poster.replace(thumb)
            try:
                movie.replace(target)
            except OSError:
                thumb.unlink(missing_ok=True)
                raise
            ctx.progress(1.0, "save")
        return [Result.make(job, target, video.name, time.perf_counter() - started, str(thumb),
                            width=width, height=height, fps=media.STORYBOARD_FPS,
                            duration=round(duration, 2))]

    def _plan(self, spec: Any, job: Job) -> tuple[Plan, float]:
        """The memory plan for the job and the video memory it needs."""
        if self._hardware is None:
            return Plan(), 0.0
        width, height = int(job.get("width", spec.native[0])), int(job.get("height", spec.native[1]))
        frames = 1
        if spec.kind in ("image", "video"):  # memory depends on what the model draws, not the final size
            width, height, _route = advisor.resolution_route(spec, width, height)
        if spec.kind == "video":
            seconds = job.get("seconds")
            frames, _capped = advisor.video_frames(spec, job.get("frames"),
                                                   float(seconds) if seconds else None)
        scale = advisor.work_scale(spec, width, height, frames)
        reference = str(job.get("reference_mode") or "") if job.get("reference") else ""
        fit = advisor.assess(spec, self._hardware, mode=self._settings.performance_mode, scale=scale,
                             reference=reference)
        if not fit.ok:
            raise EngineError("does_not_fit", spec.name)
        return fit.plan, fit.need_vram_gb

    def _attempt(self, spec: Any, plan: Plan, job: Job, ctx: Context) -> list[Any]:
        """Run a job, stepping down to a leaner memory plan if the GPU runs out."""
        while True:
            try:
                engine = self._ensure_engine(spec, plan, ctx)
                return engine.generate(job, ctx)
            except Exception as exc:
                # Sequential offload was not validated for packed GGUF and NF4 parameters.
                lower = plan.downgraded() if spec.gguf_transformer is None else None
                if not is_oom(exc) or lower is None:
                    raise
                log.warning("out of memory in mode %s, retrying as %s", plan.mode, lower.mode)
                self._drop_engine()
                ctx.progress(0.0, "retry_low_memory")
                plan = lower

    def _ensure_engine(self, spec: Any, plan: Plan, ctx: Context) -> Engine:
        engine = self._engine
        if engine is not None and engine.spec.id == spec.id and engine.plan == plan:
            return engine
        self._drop_engine(keep_claim=True)  # the memory for the new model is already claimed
        engine = create_engine(spec, plan)
        try:
            engine.load(ctx)
            ctx.check()
        except BaseException:
            engine.unload()
            if self._memory is not None:
                self._memory.released("generation")  # nothing of it stayed on the card
            raise
        self._engine = engine
        self.model_changed.emit(spec.id)
        return engine

    def _drop_engine(self, keep_claim: bool = False) -> None:
        with self._busy:
            if self._engine is not None:
                try:
                    self._engine.unload()
                except Exception:
                    log.exception("unload failed")
                self._engine = None
                self.model_changed.emit("")
            free_memory()
            if self._memory is not None and not keep_claim:
                self._memory.released("generation")
