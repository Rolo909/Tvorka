"""Helper buttons under a text field (improve, translate…) and the proposal to apply or drop.

The chat model writes a proposal; the field changes only when the user presses "Apply",
and the proposal can be edited first. The microphone sits at the end of the row.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tvorka.core.llm import prompts
from tvorka.core.llm.prompts import Task
from tvorka.gui import icons
from tvorka.gui.widgets.basic import label
from tvorka.gui.widgets.mic import MicButton
from tvorka.i18n import messages, tr


@dataclass
class Action:
    name: str
    label: str
    tip: str
    build: Callable[[], Task | None]  # None: nothing to work on
    apply: Callable[[str], None]
    visible: Callable[[], bool] = lambda: True
    vision: bool = False  # the model must see the picture
    parse: Callable[[str], tuple[str, str]] | None = None  # answer -> (note, proposal)
    title: str = ""  # above the proposal
    icon: str = ""


class AssistBar(QWidget):
    def __init__(self, page: Any, actions: list[Action], dictation: QPlainTextEdit | None = None) -> None:
        super().__init__()
        self.page, self.actions = page, actions
        self._request = 0
        self._action: Action | None = None
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.buttons: dict[str, QToolButton] = {}
        for action in actions:
            button = QToolButton()
            button.setText(action.label)
            button.setToolTip(action.tip)
            button.setProperty("role", "ghost")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if action.icon:
                button.setIcon(icons.icon(action.icon))
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.clicked.connect(lambda _=False, a=action: self.run(a))
            row.addWidget(button)
            self.buttons[action.name] = button
        row.addStretch(1)
        if dictation is not None:
            page.mic = MicButton(page, dictation)
            row.addWidget(page.mic)
        box.addLayout(row)

        self.panel = QFrame()
        self.panel.setObjectName("Banner")
        inner = QVBoxLayout(self.panel)
        inner.setContentsMargins(10, 8, 10, 10)
        inner.setSpacing(6)
        self.title = label("", "caption")
        inner.addWidget(self.title)
        self.note = label("", "warn", wrap=True)
        inner.addWidget(self.note)
        self.proposal = QPlainTextEdit()
        self.proposal.setFixedHeight(84)
        self.proposal.setAccessibleName(tr("Proposal"))
        inner.addWidget(self.proposal)
        actions_row = QHBoxLayout()
        actions_row.addStretch(1)
        self.drop = QPushButton(tr("Cancel"))
        self.drop.setProperty("role", "ghost")
        self.drop.clicked.connect(self.dismiss)
        self.apply_button = QPushButton(tr("Apply"))
        self.apply_button.setProperty("role", "accent")
        self.apply_button.clicked.connect(self._apply)
        actions_row.addWidget(self.drop)
        actions_row.addWidget(self.apply_button)
        inner.addLayout(actions_row)
        self.panel.setVisible(False)
        box.addWidget(self.panel)  # the page calls refresh() once its fields exist

    def refresh(self) -> None:
        """Show only the helpers that have something to work on now."""
        for action in self.actions:
            self.buttons[action.name].setVisible(bool(action.visible()))

    def run(self, action: Action) -> None:
        task = action.build()
        if task is None:
            return
        self.dismiss()
        self._action = action
        self.title.setText(action.title or action.label)
        self.note.setVisible(False)
        self.proposal.setPlainText(tr("The chat model is working on it…"))
        self.proposal.setEnabled(False)
        self.apply_button.setEnabled(False)
        self.panel.setVisible(True)
        assistant = self.page.services.assistant
        self._request = assistant.ask(task, self._done, self._failed, vision=action.vision)

    def _done(self, answer: str) -> None:
        self._request = 0
        action = self._action
        if action is None:
            return
        note, text = action.parse(answer) if action.parse else ("", prompts.clean(answer))
        if not text:
            self._failed("empty")
            return
        self.note.setText(note)
        self.note.setVisible(bool(note))
        self.proposal.setPlainText(text)
        self.proposal.setEnabled(True)
        self.apply_button.setEnabled(True)

    def _failed(self, code: str) -> None:
        self._request = 0
        self.panel.setVisible(False)
        if code == "cancelled":
            return
        texts = {
            "no_chat_model": tr("This needs a chat model. Download one on the Models page (Chat) — "
                                "Qwen3.5 4B suits most computers."),
            "no_vision": tr("This needs a chat model that sees images, with its image file downloaded."),
            "empty": tr("The chat model gave an empty answer. Try again."),
        }
        toasts = getattr(self.page, "toasts", None)
        if toasts is not None:
            toasts.show(texts.get(code) or messages.llm_error(code), "warn")

    def _apply(self) -> None:
        if self._action is not None:
            self._action.apply(self.proposal.toPlainText().strip())
        self.dismiss()

    def dismiss(self) -> None:
        if self._request:
            self.page.services.assistant.cancel(self._request)
            self._request = 0
        self._action = None
        self.panel.setVisible(False)
