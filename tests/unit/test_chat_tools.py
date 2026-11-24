"""Tools in the chat: the model proposes a picture, the user decides; on the llama-server stand-in."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("pytestqt")

from PIL import Image
from test_advisor import machine
from test_chat_worker import stub_command
from test_stt import write_wav

from tvorka.core import chats
from tvorka.core.attachments import Attachment
from tvorka.core.chats import Conversation, Message
from tvorka.core.jobs import Job, Result
from tvorka.core.llm import runtime
from tvorka.core.llm.client import join_tool_calls
from tvorka.core.settings import Settings
from tvorka.gui.services import Services
from tvorka.i18n import set_language


def test_tool_call_pieces_are_glued() -> None:
    pieces = [{"index": 0, "name": "generate_image", "arguments": ""},
              {"index": 0, "name": "", "arguments": '{"prom'},
              {"index": 0, "name": "", "arguments": 'pt": "x"}'},
              {"index": 1, "name": "speak", "arguments": "{broken"}]
    assert join_tool_calls(pieces) == [{"name": "generate_image", "arguments": {"prompt": "x"}},
                                       {"name": "speak", "arguments": None}]
    proposals = chats.tool_proposals([*join_tool_calls(pieces), {"name": "rm_rf", "arguments": {}}])
    assert [p["status"] for p in proposals] == ["proposed", "invalid", "invalid"]


def test_proposals_reach_the_model_as_text() -> None:
    answer = Message("assistant", "Sure!", tools=[{"name": "generate_image", "value": "a lighthouse",
                                                   "status": "done", "paths": ["x.png"]}])
    conv = Conversation(messages=[Message("user", "draw"), answer, Message("user", "more")])
    sent, _ = chats.context_messages(conv, 8192)
    assert sent[2]["content"] == "Sure!\n[generate_image: 'a lighthouse' — created]"
    assert chats.request_params(conv, False, tools=True)["tools"] == chats.TOOLS
    assert "tools" not in chats.request_params(conv, False)


def test_video_description_disables_tools_only_for_that_message() -> None:
    video = Attachment("clip.mp4", "video", text_only=True)
    conv = Conversation(messages=[Message("user", "Describe the video", attachments=[video.to_dict()])])
    conv = Conversation.from_dict(conv.to_dict())
    assert "tools" not in chats.request_params(conv, False, tools=True)

    conv.messages.append(Message("user", "Make a picture"))
    assert chats.request_params(conv, False, tools=True)["tools"] == chats.TOOLS


@pytest.fixture
def window(tmp_path: Path, qapp, qtbot, monkeypatch: pytest.MonkeyPatch):
    from tvorka.app import open_window

    set_language("ru")
    services = Services(Settings(models_dir=str(tmp_path / "m"), output_dir=str(tmp_path / "o"),
                                 welcome_done=True))
    services.hardware = machine(8)
    monkeypatch.setattr(services, "installed", lambda spec: True)
    monkeypatch.setattr(services.store, "chat_files", lambda spec: (tmp_path / "m.gguf", None))
    monkeypatch.setattr(services.store, "chat_mtp", lambda spec: None)
    monkeypatch.setattr(runtime, "server_path", lambda store, spec: tmp_path / "llama-server")
    services.chat_worker._command = stub_command
    services.chat_worker.start()
    win = open_window(qapp, services)
    qtbot.addWidget(win)
    chat = win.page("chat")
    win.open_page(win.pages.index(chat))
    chat.select_model("unsloth/Qwen3.5-2B-GGUF")  # a model with tools in the catalog
    yield win
    services.chat_worker.shutdown()
    services.chat_worker.wait(10_000)


def ask(chat, qtbot, text: str) -> None:
    chat.text.setPlainText(text)
    chat.generate()
    qtbot.waitUntil(lambda: not chat.session.busy, timeout=20_000)


def card_buttons(chat) -> list[str]:
    from PySide6.QtWidgets import QPushButton

    from tvorka.gui.widgets.chat_message import ToolCard

    cards = chat._views[-1].findChildren(ToolCard)
    return [b.text() for card in cards for b in card.findChildren(QPushButton)]


def test_nothing_is_created_without_the_user(window, qtbot, monkeypatch) -> None:
    chat = window.page("chat")
    jobs: list[Job] = []
    monkeypatch.setattr(window.services.worker, "submit", lambda job: jobs.append(job) or job.id)
    ask(chat, qtbot, "draw")
    answer = chat._conv.messages[-1]
    assert answer.content == "Sure!"
    assert answer.tools == [{"name": "generate_image", "value": "a lighthouse at dusk", "status": "proposed",
                             "paths": []}]
    assert card_buttons(chat) == ["Создать", "Сначала изменить", "Отмена"]
    assert jobs == []  # only a card so far

    chat._tool_action("create", len(chat._conv.messages) - 1, 0)
    assert len(jobs) == 1 and jobs[0].kind == "image" and jobs[0].prompt == "a lighthouse at dusk"
    tag = jobs[0].params["parent"]
    assert tag == f"chat:{chat._conv.id}:{len(chat._conv.messages) - 1}:0"
    assert chat._conv.messages[-1].tools[0]["status"] == "running"
    assert window.current_page() is chat  # the user stays in the conversation

    picture = Path(window.services.settings.output_path()) / "made.png"
    picture.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "orange").save(picture)
    from dataclasses import asdict

    from tvorka.core.jobs import Result

    made = Result.make(jobs[0], picture, "SD Turbo", 1.0, seed=42)  # the engine records the seed
    window.services.worker.job_finished.emit(jobs[0].id, [asdict(made)])
    tool = chat._conv.messages[-1].tools[0]
    assert tool["status"] == "done" and tool["paths"] == [str(picture)]
    assert card_buttons(chat) == ["Открыть", "Отправить в…"]
    stored = chat.session.store.all()[0].messages[-1].tools[0]
    assert stored["status"] == "done"  # kept with the chat


def test_decline_and_edit(window, qtbot, monkeypatch) -> None:
    chat = window.page("chat")
    jobs: list[Job] = []
    monkeypatch.setattr(window.services.worker, "submit", lambda job: jobs.append(job) or job.id)
    ask(chat, qtbot, "draw")
    last = len(chat._conv.messages) - 1
    chat._tool_action("decline", last, 0)
    assert chat._conv.messages[last].tools[0]["status"] == "declined" and jobs == []
    ask(chat, qtbot, "draw")
    last = len(chat._conv.messages) - 1
    chat._tool_action("edit", last, 0)
    image = window.page("image")
    assert window.current_page() is image and image.prompt.toPlainText() == "a lighthouse at dusk"
    assert jobs == [] and chat._conv.messages[last].tools[0]["status"] == "sent"


def test_broken_call_and_tools_turned_off(window, qtbot) -> None:
    chat = window.page("chat")
    ask(chat, qtbot, "draw broken")
    assert chat._conv.messages[-1].tools[0]["status"] == "invalid"
    assert "Создать" not in card_buttons(chat)
    chat.tools.setChecked(False)
    assert chat._conv.tools is False
    ask(chat, qtbot, "draw")  # the request goes without tools: a plain answer
    assert chat._conv.messages[-1].tools == [] and chat._conv.messages[-1].content == "Hello, world"


def test_read_answer_plays_local_speech_in_chat(window, qtbot, monkeypatch, tmp_path) -> None:
    chat = window.page("chat")
    speech = window.page("speech")
    speech.select_model("silero/v4_ru")
    speech.text.setPlainText("A speech draft")
    jobs: list[Job] = []
    played: list[str] = []
    monkeypatch.setattr(window.services.worker, "submit", jobs.append)
    monkeypatch.setattr(chat.audio, "play", played.append)
    ask(chat, qtbot, "hi")
    view = chat._views[-1]
    next(button for button in view.buttons if button.toolTip() == "Озвучить ответ").click()
    chat._read_answer(len(chat._conv.messages) - 1)
    [job] = jobs
    assert job.model_id == "silero/v4_ru" and job.prompt == "Hello, world"
    assert speech.text.toPlainText() == "A speech draft"
    assert window.current_page() is chat and not played

    path = write_wav(tmp_path / "answer.wav")
    result = asdict(Result.make(job, path, "Silero", 0.1))
    window.services.worker.job_finished.emit(job.id, [result])
    assert played == [str(path)]
    assert card_buttons(chat) == ["Воспроизвести", "Открыть", "Отправить в…"]
    assert speech._rows[0].path == str(path)
    tool = chat.session.store.all()[0].messages[-1].tools[-1]
    assert tool["status"] == "done" and tool["paths"] == [str(path)]
    chat._read_answer(len(chat._conv.messages) - 1)
    assert jobs == [job] and played == [str(path), str(path)]


def test_failed_chat_speech_can_be_retried_and_cloud_voice_opens_speech(window, qtbot, monkeypatch) -> None:
    chat = window.page("chat")
    speech = window.page("speech")
    speech.select_model("silero/v4_ru")
    jobs: list[Job] = []
    monkeypatch.setattr(window.services.worker, "submit", jobs.append)
    ask(chat, qtbot, "hi")
    index = len(chat._conv.messages) - 1
    chat._read_answer(index)
    window.services.worker.job_failed.emit(jobs[-1].id, "failed", "")
    assert chat._conv.messages[index].tools[-1]["status"] == "failed"
    chat._read_answer(index)
    window.services.worker.job_cancelled.emit(jobs[-1].id)
    assert len(jobs) == 2 and not window.services.chat_speech_jobs

    speech.select_model("edge/online")
    chat._read_answer(index)
    assert len(jobs) == 2 and window.current_page() is speech
    assert speech.text.toPlainText() == "Hello, world"
