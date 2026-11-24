"""Cancellation bookkeeping of GenerationWorker (no thread is started)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from tvorka.core.catalog import Catalog
from tvorka.core.jobs import History, Job
from tvorka.core.settings import Settings
from tvorka.core.store import ModelStore
from tvorka.workers import generation
from tvorka.workers.generation import GenerationWorker


@pytest.fixture
def worker(tmp_path: Path) -> GenerationWorker:
    settings = Settings(models_dir=str(tmp_path / "m"), output_dir=str(tmp_path / "o"))
    return GenerationWorker(settings, Catalog(), ModelStore(settings), History(tmp_path / "h.json"))


def test_cancel_all_does_not_affect_later_jobs(worker: GenerationWorker) -> None:
    first, second = Job("image", "m", "a"), Job("image", "m", "b")
    worker.submit(first)
    worker.submit(second)
    worker.cancel(None)
    later = Job("image", "m", "c")
    worker.submit(later)
    assert worker._is_cancelled(first.id)
    assert worker._is_cancelled(second.id)
    assert not worker._is_cancelled(later.id)


def test_cancel_one(worker: GenerationWorker) -> None:
    a, b = Job("image", "m", "a"), Job("image", "m", "b")
    worker.submit(a)
    worker.submit(b)
    worker.cancel(b.id)
    assert not worker._is_cancelled(a.id)
    assert worker._is_cancelled(b.id)
    worker.cancel(12345)  # unknown id: ignored
    assert 12345 not in worker._cancel


def test_cancellation_at_the_end_of_load_releases_the_engine(worker: GenerationWorker, monkeypatch) -> None:
    job = Job("image", "stabilityai/sd-turbo", "A lighthouse")
    worker.submit(job)
    unloaded = []
    engine = SimpleNamespace(load=lambda _ctx: worker.cancel(job.id), unload=lambda: unloaded.append(True))
    monkeypatch.setattr(generation, "create_engine", lambda _spec, _plan: engine)
    cancelled = []
    worker.job_cancelled.connect(cancelled.append)
    worker._run_job(job)
    assert unloaded == [True] and cancelled == [job.id]
    assert not worker.loaded_model
