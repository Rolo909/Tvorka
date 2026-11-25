from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("pytestqt")

from test_advisor import machine
from test_chat_worker import stub_command

from tvorka.core.jobs import Job, Result, output_file
from tvorka.core.llm import runtime
from tvorka.core.settings import Settings
from tvorka.engines.base import Context
from tvorka.gui.pages.code import CodePage
from tvorka.gui.services import Services
from tvorka.i18n import set_language
from tvorka.workers import generation


@pytest.fixture
def services(tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(models_dir=str(tmp_path / "models"), output_dir=str(tmp_path / "output"))
    services = Services(settings)
    services.hardware = machine()
    set_language("en")
    monkeypatch.setattr(services, "installed", lambda spec: spec.kind == "chat")
    monkeypatch.setattr(services.store, "chat_files", lambda _spec: (tmp_path / "model.gguf", None))
    monkeypatch.setattr(runtime, "server_path", lambda _store, _spec: tmp_path / "llama-server")
    services.chat_worker._command = stub_command
    services.chat_worker.start()
    yield services
    services.code.cancel()
    services.chat_worker.shutdown()
    assert services.code.wait(5000)
    assert services.chat_worker.wait(10_000)
    set_language("ru")


@pytest.fixture
def page(services: Services, tmp_path: Path, qtbot) -> CodePage:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('before')\n", encoding="utf-8")
    page = CodePage(services, None)
    qtbot.addWidget(page)
    page.model.setCurrentIndex(page.model.findData("unsloth/Qwen3.5-2B-GGUF"))
    assert page.open_project(project, {"main.py"})
    qtbot.waitUntil(lambda: page.tree.checked() == ("main.py",))
    return page


def test_agent_uses_same_server_and_applies_only_after_confirmation(page: CodePage, qtbot) -> None:
    page.mode.set_value("agent")
    project_file = page.workspace.root / "main.py"
    page.text.setPlainText("Change print output and check it")
    page.send_task.click()
    qtbot.waitUntil(lambda: page._approval is not None, timeout=15_000)
    assert page._approval.approval.kind == "write"
    assert project_file.read_text() == "print('before')\n"

    page._approval._apply()
    qtbot.waitUntil(lambda: page._approval is not None, timeout=15_000)
    assert page._approval.approval.label == "echo verified"
    with qtbot.waitSignal(page.worker.finished, timeout=15_000):
        page._approval._apply()

    assert "verified" in page.output.toPlainText()
    assert project_file.read_text() == "print('after')\n"
    session = page.worker.store.load(page.workspace)
    tool_results = [item for item in session.messages if item["role"] == "tool"]
    assert [item["tool_call_id"] for item in tool_results] == [f"code_{i}" for i in range(4)]
    page.undo.click()
    assert project_file.read_text() == "print('before')\n"


def test_edits_approval_survives_rebuild_and_can_be_rejected(page: CodePage, qtbot) -> None:
    page.mode.set_value("edit")
    page.text.setPlainText("Change the text printed by main.py")
    page.send_task.click()
    qtbot.waitUntil(lambda: page._approval is not None, timeout=15_000)
    page.save_state()
    rebuilt = CodePage(page.services, None)
    qtbot.addWidget(rebuilt)

    assert rebuilt._approval is not None and "print('after')" in rebuilt.diff.toPlainText()
    with qtbot.waitSignal(rebuilt.worker.finished, timeout=15_000):
        rebuilt._approval._reject()

    assert (rebuilt.workspace.root / "main.py").read_text() == "print('before')\n"
    assert not rebuilt.worker.store.checkpoints(rebuilt.workspace).steps()


def test_stop_releases_pending_approval_and_keeps_the_file(page: CodePage, qtbot) -> None:
    page.text.setPlainText("Change the text printed by main.py")
    page.send_task.click()
    qtbot.waitUntil(lambda: page._approval is not None, timeout=15_000)

    with qtbot.waitSignal(page.worker.settled) as result:
        page.cancel()

    assert result.args == ["cancelled"]
    assert (page.workspace.root / "main.py").read_text() == "print('before')\n"


def test_image_tool_approves_stages_and_undoes_project_asset(page: CodePage, qtbot,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    def generate(job: Job, ctx: Context) -> list[Result]:
        assert job.get("preview")
        target = output_file(ctx.settings.output_path(), "image", "png")
        Image.new("RGB", (64, 64), "blue").save(target)
        return [Result.make(job, target, "Test image", 0)]

    services = page.services
    monkeypatch.setattr(services, "installed",
                        lambda spec: spec.kind == "chat" or spec.id == "stabilityai/sd-turbo")
    monkeypatch.setattr(services.worker, "_generate", generate)
    monkeypatch.setattr(generation, "free_memory", lambda: None)
    services.worker.start()
    try:
        page.mode.set_value("agent")
        page.text.setPlainText("Create a local project image")
        page.send_task.click()
        qtbot.waitUntil(lambda: page._approval is not None, timeout=15_000)
        target = page.workspace.root / "assets" / "icon.png"
        assert page._approval.approval.kind == "image" and not target.exists()

        with qtbot.waitSignal(page.worker.finished, timeout=15_000):
            page._approval._apply()

        assert target.read_bytes().startswith(b"\x89PNG") and not services.history.items()
        page.undo.click()
        assert not target.exists()
    finally:
        services.worker.shutdown()
