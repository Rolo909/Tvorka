"""The chat model helping other sections, on the llama-server stand-in (it always answers "Hello, world")."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("pytestqt")

from test_advisor import machine
from test_chat_worker import stub_command

from tvorka.core.jobs import Job
from tvorka.core.llm import runtime
from tvorka.core.settings import Settings
from tvorka.gui.services import Services
from tvorka.i18n import set_language


class Toasts:
    def __init__(self) -> None:
        self.shown: list[str] = []

    def show(self, text: str, *args: object, **kwargs: object) -> None:
        self.shown.append(text)


@pytest.fixture
def services(tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch):
    set_language("ru")
    services = Services(Settings(models_dir=str(tmp_path / "m"), output_dir=str(tmp_path / "o")))
    services.hardware = machine(8)
    services.settings.remember("chat", model="unsloth/Qwen3.5-2B-GGUF")
    monkeypatch.setattr(services, "installed", lambda spec: True)
    monkeypatch.setattr(services.store, "chat_files", lambda spec: (tmp_path / "m.gguf", None))
    monkeypatch.setattr(services.store, "chat_mtp", lambda spec: None)
    monkeypatch.setattr(runtime, "server_path", lambda store, spec: tmp_path / "llama-server")
    services.chat_worker._command = stub_command
    services.chat_worker.start()
    yield services
    services.chat_worker.shutdown()
    services.chat_worker.wait(10_000)


def page_of(services: Services, qtbot, cls):
    page = cls(services, None)
    page.toasts = Toasts()
    qtbot.addWidget(page)
    return page


def test_improve_shows_a_proposal_to_apply(services: Services, qtbot) -> None:
    from tvorka.gui.pages.image import ImagePage

    page = page_of(services, qtbot, ImagePage)
    page.prompt.setPlainText("маяк в шторм")
    bar = page.assist
    assert not bar.buttons["improve"].isHidden() and not bar.buttons["translate"].isHidden()
    assert bar.buttons["critique"].isHidden() and bar.buttons["describe"].isHidden()  # nothing to look at
    bar.buttons["improve"].click()
    assert bar.panel.isVisibleTo(page) and not bar.apply_button.isEnabled()
    qtbot.waitUntil(lambda: bar.apply_button.isEnabled(), timeout=20_000)
    assert bar.proposal.toPlainText() == "Hello, world"
    assert page.prompt.toPlainText() == "маяк в шторм"  # nothing changes until "Apply"
    bar.proposal.setPlainText("Hello, world, edited")
    bar.apply_button.click()
    assert page.prompt.toPlainText() == "Hello, world, edited" and not bar.panel.isVisibleTo(page)
    assert services.chat.conversations == []  # the helper does not start a chat


def test_prompt_is_translated_before_creating(services: Services, qtbot, monkeypatch) -> None:
    from tvorka.gui.pages.image import ImagePage

    page = page_of(services, qtbot, ImagePage)
    jobs: list[Job] = []
    monkeypatch.setattr(services.worker, "submit", lambda job: jobs.append(job) or job.id)
    page.prompt.setPlainText("кот на подоконнике")
    page.generate()
    assert jobs == [] and page._translating  # waits for the translation
    qtbot.waitUntil(lambda: bool(jobs), timeout=20_000)
    assert jobs[0].prompt == "Hello, world" and jobs[0].params["prompt_original"] == "кот на подоконнике"
    assert page.prompt.toPlainText() == "кот на подоконнике"  # the field keeps what the user wrote
    page._jobs.clear()
    services.settings.auto_translate = False
    page.generate()
    assert jobs[-1].prompt == "кот на подоконнике" and "prompt_original" not in jobs[-1].params
    page.prompt.setPlainText("a cat on a windowsill")
    services.settings.auto_translate = True
    page._jobs.clear()
    page.generate()  # already English: no round trip
    assert jobs[-1].prompt == "a cat on a windowsill"


def test_text_is_prepared_for_reading(services: Services, qtbot) -> None:
    from tvorka.gui.pages.speech import SpeechPage

    page = page_of(services, qtbot, SpeechPage)
    page.text.setPlainText("В 2026 г. — 5 км")
    page.assist.buttons["prepare"].click()
    qtbot.waitUntil(lambda: page.assist.apply_button.isEnabled(), timeout=20_000)
    page.assist.apply_button.click()
    assert page.text.toPlainText() == "Hello, world"


def test_translation_follows_the_selected_voice(services: Services, qtbot, monkeypatch) -> None:
    from tvorka.gui.pages.speech import SpeechPage

    page = page_of(services, qtbot, SpeechPage)
    page.select_model("suno/bark-small")
    page.text.setPlainText("Привет, мир")
    assert "Russian" in page._translate_task().messages[0]["content"]

    page.voice.setCurrentIndex(page.voice.findData("v2/en_speaker_6"))
    assert "English" in page._translate_task().messages[0]["content"]
    page.assist.buttons["translate"].click()
    qtbot.waitUntil(lambda: page.assist.apply_button.isEnabled(), timeout=20_000)
    assert page.text.toPlainText() == "Привет, мир"
    assert page.assist.proposal.toPlainText() == "Hello, world"

    page.voice.setCurrentIndex(page.voice.findData("v2/ru_speaker_3"))
    assert not page.assist.panel.isVisibleTo(page)
    page.select_model("silero/v3_en")
    page.assist.buttons["translate"].click()
    qtbot.waitUntil(lambda: page.assist.apply_button.isEnabled(), timeout=20_000)
    page.assist.apply_button.click()

    jobs: list[Job] = []
    monkeypatch.setattr(services.worker, "submit", lambda job: jobs.append(job) or job.id)
    page.generate()
    assert jobs[0].prompt == "Hello, world" and jobs[0].model_id == "silero/v3_en"


def test_without_a_chat_model_the_helper_says_what_to_do(services: Services, qtbot, monkeypatch) -> None:
    from tvorka.gui.pages.image import ImagePage

    page = page_of(services, qtbot, ImagePage)
    monkeypatch.setattr(services, "installed", lambda spec: spec.kind != "chat")
    page.prompt.setPlainText("маяк")
    page.assist.buttons["improve"].click()
    assert not page.assist.panel.isVisibleTo(page) and "нужна чат-модель" in page.toasts.shown[-1]
    jobs: list[Job] = []
    monkeypatch.setattr(services.worker, "submit", lambda job: jobs.append(job) or job.id)
    page.generate()  # no chat model: the prompt goes untranslated, without waiting
    assert jobs and jobs[0].prompt == "маяк"


def test_looking_at_a_picture_needs_a_model_that_sees(services: Services, qtbot, tmp_path: Path) -> None:
    from PIL import Image

    from tvorka.gui.pages.image import ImagePage

    page = page_of(services, qtbot, ImagePage)
    Image.new("RGB", (64, 64), "red").save(tmp_path / "ref.png")
    page.dropzone.set_path(str(tmp_path / "ref.png"))
    page._update_action()
    assert not page.assist.buttons["describe"].isHidden()
    page.assist.buttons["describe"].click()  # the projector is not on disk in this test
    assert "видит картинки" in page.toasts.shown[-1]
