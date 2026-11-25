"""A storyboard from Chat through the queue to a real MP4 with synchronized sound."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import av
import numpy as np
import pytest
from PIL import Image

pytest.importorskip("pytestqt")

from test_advisor import machine
from test_chat_worker import stub_command

from tvorka.core import storyboard
from tvorka.core.catalog import ModelSpec
from tvorka.core.chats import Message
from tvorka.core.jobs import Job, Result, output_file
from tvorka.core.llm import runtime
from tvorka.core.settings import Settings
from tvorka.engines import media
from tvorka.engines.base import Context, Engine, EngineError
from tvorka.gui.pages.chat import ChatPage
from tvorka.gui.pages.gallery import GalleryPage
from tvorka.gui.services import Services
from tvorka.workers import generation


@pytest.fixture
def services(tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(models_dir=str(tmp_path / "models"), output_dir=str(tmp_path / "output"))
    services = Services(settings)
    services.hardware = machine(8)
    services.catalog.add_user(ModelSpec("test/animation", "Animation test", "video", source="local",
                                        path=str(tmp_path), native=[64, 48], reference=["i2v"],
                                        defaults={"frames": 4, "fps": 8}))
    installed = {"stabilityai/sd-turbo", "test/animation", "silero/v4_ru"}
    monkeypatch.setattr(services, "installed", lambda spec: spec.kind in {"chat", "runtime"}
                        or spec.id in installed)
    monkeypatch.setattr(services.store, "chat_files", lambda _spec: (tmp_path / "test.gguf", None))
    monkeypatch.setattr(runtime, "server_path", lambda _store, _spec: tmp_path / "llama-server")
    monkeypatch.setattr(generation, "free_memory", lambda: None)
    services.chat_worker._command = stub_command
    services.chat_worker.start()
    services.worker.start()
    yield services
    services.chat_worker.shutdown()
    services.worker.shutdown()


@pytest.mark.parametrize("answer", ['{"scenes":[]}', '{"scenes":[{"image":"img","motion":" ",'
                                                       '"narration":"voice"}]}', '{"scenes":[1]}'])
def test_rejects_incomplete_scenes(answer: str) -> None:
    with pytest.raises(ValueError):
        storyboard.parse(answer, 1)


def test_chat_storyboard_assembles_three_edited_scenes(services: Services, qtbot,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class StubEngine(Engine):
        def load(self, _ctx: Context) -> None:
            pass

        def unload(self) -> None:
            pass

        def generate(self, job: Job, ctx: Context) -> list[Result]:
            assert not services.history.items()
            n = int(job.prompt.split()[-1])
            calls.append((job.kind, n))
            path = output_file(ctx.settings.output_path(), job.kind, job.get("format"))
            if job.kind == "image":
                Image.new("RGB", (64, 48), (n * 60, 0, 0)).save(path)
            elif job.kind == "video":
                with Image.open(job.get("reference")) as image:
                    media.write_video(np.stack([np.asarray(image)] * 4), 8, path)
            else:
                size = 36_000 if n == 2 else 12_000
                samples = (0.4 * np.sin(np.arange(size) * (0.10 + 0.01 * n))).astype(np.float32)
                media.write_audio(samples, 48_000, path)
            return [Result.make(job, path, self.spec.name, 0)]

    monkeypatch.setattr(generation, "create_engine", StubEngine)
    page = ChatPage(services, None)
    qtbot.addWidget(page)
    page._conv.messages.append(Message("user", "Previous idea"))
    services.chat.save(page._conv)
    page.text.setPlainText("A lighthouse on a stormy evening")
    page._open_storyboard()
    dialog = page._storyboard
    dialog.language.setCurrentIndex(dialog.language.findData("ru"))
    dialog.count.setValue(4)
    dialog.plan.click()
    qtbot.waitUntil(lambda: dialog.table.rowCount() == 4, timeout=15_000)
    dialog.table.setCurrentCell(3, 0)
    dialog.remove.click()
    dialog.table.setCurrentCell(1, 0)
    dialog.up.click()
    dialog.table.item(1, 2).setText("rewritten voice 1")
    assert dialog.build.isEnabled()
    with qtbot.waitSignal(services.worker.job_finished, timeout=15_000):
        dialog.build.click()

    assert calls == [(kind, n) for kind in ("image", "video", "speech") for n in (2, 1, 3)]
    [result] = services.history.items()
    assert result.prompt == "A lighthouse on a stormy evening"
    assert result.params["parent"] == f"chat:{page._conv.id}"
    assert result.params["storyboard"][1]["narration"] == "rewritten voice 1"
    assert result.params["duration"] == 1.75 and Path(result.thumb).is_file()
    with av.open(result.path) as film:
        video, audio = film.streams.video[0], film.streams.audio[0]
        assert float(video.duration * video.time_base) == 1.75
        assert float(audio.duration * audio.time_base) == pytest.approx(1.75, abs=0.03)
        pictures = list(film.decode(video))
    assert len(pictures) == 42
    assert [pictures[i].to_ndarray(format="rgb24")[0, 0, 0].item() for i in (0, 18, 30)] \
        == pytest.approx([120, 60, 180], abs=4)
    samples, rate = media.read_audio(Path(result.path))
    assert np.abs(samples[int(0.6 * rate):int(0.7 * rate)]).max() > .2  # long opening voice
    assert np.abs(samples[int(1.1 * rate):int(1.2 * rate)]).max() < .02  # silence after voice two
    assert np.abs(samples[int(1.3 * rate):int(1.4 * rate)]).max() > .2  # third voice starts on its cut
    assert not list(services.settings.output_path().glob(".tvorka-storyboard-*"))
    assert not dialog.gallery.isHidden()
    dialog.reject()
    gallery = GalleryPage(services, None)
    qtbot.addWidget(gallery)
    gallery.shown()
    gallery.grid.setCurrentRow(0)
    assert gallery.grid.count() == 1 and gallery.lineage.isEnabled()


@pytest.mark.parametrize("cancelled", [False, True])
def test_interrupted_scene_cleans_up(services: Services, qtbot, monkeypatch: pytest.MonkeyPatch,
                                     cancelled: bool) -> None:
    job = Job("video", "test/animation", "Idea", {
        "storyboard": [asdict(storyboard.Scene("a", "b", "c"))],
        "image_model": "stabilityai/sd-turbo", "speech_model": "silero/v4_ru",
    })

    def generate(part: Job, ctx: Context) -> list[Result]:
        if part.kind == "video":
            if cancelled:
                services.worker.cancel(job.id)
                ctx.check()
            raise EngineError("failed", "animation failed")
        path = output_file(ctx.settings.output_path(), part.kind, part.get("format"))
        path.write_bytes(b"temporary image")
        return [Result.make(part, path, "test", 0)]

    monkeypatch.setattr(services.worker, "_generate", generate)
    signal = services.worker.job_cancelled if cancelled else services.worker.job_failed
    with qtbot.waitSignal(signal, timeout=5_000) as stopped:
        services.worker.submit(job)
    assert stopped.args == ([job.id] if cancelled else [job.id, "failed", "animation failed"])
    assert not services.history.items()
    assert not list(services.settings.output_path().iterdir())
