"""Chat page: talk to a local language model; conversations on the left, the current one on the right."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QFont,
    QGuiApplication,
    QHideEvent,
    QImage,
    QKeySequence,
    QShortcut,
    QTextDocumentFragment,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from tvorka.core import attachments, chats
from tvorka.core.advisor import DEFAULT_CTX, NO, Fit, LlmPlan
from tvorka.core.attachments import Attachment, AttachmentError
from tvorka.core.catalog import ModelSpec
from tvorka.core.chats import Conversation, Message
from tvorka.gui import handoff, icons, theme
from tvorka.gui.handoff import Asset, Route
from tvorka.gui.pages.base import Page
from tvorka.gui.pages.speech import SpeechPage
from tvorka.gui.services import Services
from tvorka.gui.widgets.basic import Card, Field, Segmented, SliderField, label, tool_button
from tvorka.gui.widgets.chat_attachments import AttachmentChip, ComposerEdit, local_files
from tvorka.gui.widgets.chat_audio import ChatAudio
from tvorka.gui.widgets.chat_message import MessageView
from tvorka.gui.widgets.feedback import ToastHost
from tvorka.gui.widgets.fit import FitBanner
from tvorka.gui.widgets.mic import MicButton
from tvorka.gui.widgets.model_card import chat_download_files, chat_download_gb, size_text
from tvorka.gui.widgets.storyboard import StoryboardDialog
from tvorka.i18n import messages, tr
from tvorka.workers.downloads import run_async

MEMORY_OPTIONS = (0, 4096, 8192, 16384, 32768)
# Proposals of the model -> the section that makes them, and how it takes the text.
TOOL_ROUTES = {"generate_image": ("image", "prompt"), "generate_video": ("video", "prompt"),
               "speak": ("speech", "text")}


def role_names() -> dict[str, str]:
    return {
        "assistant": tr("Assistant"),
        "image_prompts": tr("Image prompt writer"),
        "video_director": tr("Video director"),
        "screenwriter": tr("Screenwriter"),
        "translator": tr("Translator"),
        "voice_editor": tr("Text for voice-over"),
    }


class ChatPage(Page):
    key = "chat"
    icon = "chat"

    def __init__(self, services: Services, toasts: ToastHost | None) -> None:
        super().__init__(services, toasts)
        self.session = services.chat
        self._conv = Conversation()
        self._spec: ModelSpec | None = None
        self._editing = -1  # index of the user message being rewritten
        self._views: list[MessageView] = []
        self._live: MessageView | None = None
        self._chips: list[AttachmentChip] = []
        self._reading = 0  # files still being read
        self._audio_chat = ""
        self._storyboard: StoryboardDialog | None = None
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_list())
        layout.addWidget(self._build_main(), 1)

        self.session.listed.connect(self._fill_list)
        self.session.changed.connect(self._on_changed)
        self.session.streaming.connect(self._on_streaming)
        self.session.state_changed.connect(self._update_action)
        self.session.failed.connect(self._on_failed)
        services.hardware_ready.connect(self._on_hardware)
        services.models_changed.connect(self._fill_models)
        downloads = services.downloads
        for signal in (downloads.progress, downloads.cancelled, downloads.finished):
            signal.connect(lambda *_args: self._update_action())
        services.downloads.failed.connect(self._on_download_failed)
        services.worker.job_finished.connect(self._on_job_finished)  # works the model proposed
        services.worker.job_failed.connect(self._on_speech_failed)
        services.worker.job_cancelled.connect(self._finish_chat_speech)
        self._fill_models()
        self._restore()

    def title(self) -> str:
        return tr("Chat")

    # ============================================================ layout
    def _build_list(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("ChatList")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setFixedWidth(248)
        box = QVBoxLayout(panel)
        box.setContentsMargins(12, 22, 12, 12)
        box.setSpacing(8)
        self.new_button = QPushButton(tr("New chat"))
        self.new_button.setProperty("role", "accent")
        self.new_button.setIcon(icons.icon("plus", "accent_text"))
        self.new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_button.clicked.connect(self.new_chat)
        box.addWidget(self.new_button)
        storyboard = QPushButton(tr("Video from an idea"))
        storyboard.clicked.connect(self._open_storyboard)
        box.addWidget(storyboard)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search chats"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill_list)
        box.addWidget(self.search)
        self.list = QListWidget()
        self.list.setAccessibleName(tr("Chats"))
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)  # a long title ends with "…"
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._list_menu)
        self.list.itemClicked.connect(self._item_clicked)
        delete = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.list, self._delete_selected)
        delete.setContext(Qt.ShortcutContext.WidgetShortcut)
        box.addWidget(self.list, 1)
        self.list_empty = label(tr("Your conversations will be listed here."), "faint", wrap=True)
        box.addWidget(self.list_empty)
        return panel

    def _open_storyboard(self) -> None:
        if self._storyboard is None:
            parent = f"chat:{self._conv.id}" if self.session.get(self._conv.id) else ""
            self._storyboard = StoryboardDialog(self, self.text.toPlainText(), parent)
            self._storyboard.finished.connect(self._storyboard_closed)
        self._storyboard.show()
        self._storyboard.raise_()
        self._storyboard.activateWindow()

    def _storyboard_closed(self, _result: int) -> None:
        self._storyboard = None

    def _build_main(self) -> QWidget:
        main = QWidget()
        column = QVBoxLayout(main)
        column.setContentsMargins(24, 18, 22, 16)
        column.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.heading = label("", "heading")
        self.heading.setMinimumWidth(80)
        head.addWidget(self.heading, 1)
        self.model_box = QComboBox()
        self.model_box.setAccessibleName(tr("Model"))
        self.model_box.setMinimumWidth(200)
        self.model_box.currentIndexChanged.connect(self._model_selected)
        self.role_box = QComboBox()
        self.role_box.setAccessibleName(tr("Role"))
        for key, name in role_names().items():
            self.role_box.addItem(name, key)
        self.role_box.currentIndexChanged.connect(self._role_selected)
        self.params_button = tool_button("settings", tr("Chat settings"))
        self.params_button.setCheckable(True)
        self.params_button.toggled.connect(lambda on: self.params.setVisible(on))
        head.addWidget(self.model_box)
        head.addWidget(self.role_box)
        head.addWidget(self.params_button)
        column.addLayout(head)

        self.fit_banner = FitBanner()
        column.addWidget(self.fit_banner)
        column.addWidget(self._build_params())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        self.thread = QVBoxLayout(holder)
        self.thread.setContentsMargins(0, 4, 8, 4)
        self.thread.setSpacing(14)
        self.empty = self._build_empty()
        self.thread.addWidget(self.empty)
        self.thread.addStretch(1)
        self.scroll.setWidget(holder)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._follow)
        column.addWidget(self.scroll, 1)

        self.context_note = label("", "faint", wrap=True)
        self.context_note.setVisible(False)
        column.addWidget(self.context_note)
        self.audio = ChatAudio()
        self.audio.failed.connect(self._on_audio_failed)
        column.addWidget(self.audio)
        column.addWidget(self._build_composer())
        return main

    def _build_params(self) -> QWidget:
        self.params = Card(tr("Chat settings"))
        row = QHBoxLayout()
        row.setSpacing(16)
        self.temperature = SliderField(0.0, 1.5, 0.05, 2)
        self.temperature.changed.connect(self._params_changed)
        self.auto_temperature = QCheckBox(tr("As the model's authors recommend"))
        self.auto_temperature.toggled.connect(self._params_changed)
        creativity = QWidget()
        creativity_box = QVBoxLayout(creativity)
        creativity_box.setContentsMargins(0, 0, 0, 0)
        creativity_box.setSpacing(4)
        creativity_box.addWidget(self.auto_temperature)
        creativity_box.addWidget(self.temperature)
        self.memory = Segmented([(str(v), tr("Auto") if not v else f"{v // 1024}K") for v in MEMORY_OPTIONS])
        self.memory.changed.connect(self._params_changed)
        row.addWidget(Field(tr("Creativity"), creativity,
                            tr("Lower — precise and repeatable, higher — more varied.")), 1)
        row.addWidget(Field(tr("Conversation memory"), self.memory,
                            tr("Longer memory needs more video memory.")), 1)
        self.params.body.addLayout(row)
        self.thinking = QCheckBox(tr("Think before answering"))
        self.thinking.setToolTip(tr("The model reasons first: answers are more careful but take several "
                                    "times longer. The reasoning is shown folded above the answer."))
        self.thinking.toggled.connect(self._params_changed)
        self.params.body.addWidget(self.thinking)
        self.tools = QCheckBox(tr("The model may suggest creating a picture, a video clip or a voice-over"))
        self.tools.setToolTip(tr("It shows a card under its answer; nothing is created until you press "
                                 "“Create”."))
        self.tools.toggled.connect(self._params_changed)
        self.params.body.addWidget(self.tools)
        self.instruction = QPlainTextEdit()
        self.instruction.setPlaceholderText(tr("Your own instruction for this chat, instead of the role. "
                                               "For example: answer briefly, as a film critic."))
        self.instruction.setFixedHeight(64)
        self.instruction.textChanged.connect(self._params_changed)
        self.params.body.addWidget(Field(tr("Instruction"), self.instruction))
        self.params.setVisible(False)
        return self.params

    def _build_empty(self) -> QWidget:
        empty = QWidget()
        box = QVBoxLayout(empty)
        box.setContentsMargins(0, 40, 0, 0)
        box.setSpacing(10)
        title = label(tr("What shall we talk about?"), "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(title)
        hint = label(tr("Everything stays on this computer. Pick a role above — or just start typing."),
                     "subtitle", wrap=True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(hint)
        ideas = QVBoxLayout()
        ideas.setSpacing(6)
        ideas.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        for text in (tr("Come up with a plot for a 30-second video about a lighthouse"),
                     tr("Write an image prompt: a cozy reading nook in the rain"),
                     tr("Explain in simple words how a neural network draws pictures")):
            chip = QPushButton(text)
            chip.setProperty("role", "chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, t=text: self._use_idea(t))
            ideas.addWidget(chip)
        box.addSpacing(6)
        box.addLayout(ideas)
        return empty

    def _build_composer(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Composer")
        box = QVBoxLayout(frame)
        box.setContentsMargins(12, 8, 10, 10)
        box.setSpacing(6)
        self.editing_bar = QWidget()
        bar = QHBoxLayout(self.editing_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(label(tr("Editing a message: the answers after it will be replaced."), "warn"), 1)
        cancel_edit = QPushButton(tr("Cancel"))
        cancel_edit.setProperty("role", "link")
        cancel_edit.clicked.connect(self._cancel_edit)
        bar.addWidget(cancel_edit)
        self.editing_bar.setVisible(False)
        box.addWidget(self.editing_bar)
        self.chips = QWidget()
        self.chips_row = QHBoxLayout(self.chips)
        self.chips_row.setContentsMargins(0, 0, 0, 0)
        self.chips_row.setSpacing(6)
        self.chips_row.addStretch(1)
        self.chips.setVisible(False)
        box.addWidget(self.chips)
        self.text = ComposerEdit()
        self.text.image_pasted.connect(self._add_image)
        self.text.files_pasted.connect(self.add_files)
        self.text.setPlaceholderText(tr("Message… (Ctrl+Enter — send)"))
        self.text.setAccessibleName(tr("Message"))
        self.text.setFixedHeight(84)
        self.text.textChanged.connect(self._text_changed)
        box.addWidget(self.text)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.attach = tool_button("attach", tr("Attach files: pictures, text, PDF, Word, video. "
                                               "You can also drag them here or paste with Ctrl+V."))
        self.attach.clicked.connect(self._choose_files)
        row.addWidget(self.attach)
        self.mic = MicButton(self, self.text)
        row.addWidget(self.mic)
        self.counter = label("", "mono")
        self.status = label("", "muted")
        row.addWidget(self.counter)
        row.addWidget(self.status, 1)
        self.action = QPushButton()
        self.action.setProperty("role", "primary")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self._action_clicked)
        row.addWidget(self.action)
        box.addLayout(row)
        return frame

    # ============================================================ conversations
    def _fill_list(self) -> None:
        query = self.search.text().strip().lower()
        self.list.clear()
        today = time.strftime("%Y-%m-%d")
        yesterday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        group = ""
        for conv in self.session.conversations:
            if query and query not in conv.title.lower() and not any(
                    query in m.content.lower() for m in conv.messages):
                continue
            day = time.strftime("%Y-%m-%d", time.localtime(conv.updated))
            name = tr("Today") if day == today else tr("Yesterday") if day == yesterday else tr("Earlier")
            if name != group:
                group = name
                header = QListWidgetItem(name)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header.setFont(theme.font("body", 8.5, QFont.Weight.DemiBold))
                header.setForeground(theme.color("faint"))
                self.list.addItem(header)
            item = QListWidgetItem(conv.title or tr("New chat"))
            item.setData(Qt.ItemDataRole.UserRole, conv.id)
            item.setToolTip(conv.title)
            self.list.addItem(item)
            if conv.id == self._conv.id:
                item.setSelected(True)
                self.list.setCurrentItem(item)
        self.list_empty.setVisible(not self.session.conversations)

    def _item_clicked(self, item: QListWidgetItem) -> None:
        conv = self.session.get(item.data(Qt.ItemDataRole.UserRole) or "")
        if conv is not None and conv is not self._conv:
            self.open_chat(conv)

    def open_chat(self, conv: Conversation) -> None:
        self._remember_draft()
        self._conv, self._editing = conv, -1
        self.editing_bar.setVisible(False)
        self.text.setPlainText(self._drafts().get(conv.id, ""))
        self._apply_conversation()
        self._fill_list()

    def new_chat(self) -> None:
        self._remember_draft()
        self._conv = Conversation(model=self._spec.id if self._spec else "",
                                  role=self.role_box.currentData() or chats.DEFAULT_ROLE)
        self._editing = -1
        self.editing_bar.setVisible(False)
        self.text.clear()
        self._apply_conversation()
        self._fill_list()
        self.text.setFocus()

    def _apply_conversation(self) -> None:
        """Show the conversation's model, role and settings, then its messages."""
        conv = self._conv
        for box, value in ((self.model_box, conv.model), (self.role_box, conv.role)):
            index = box.findData(value)
            if index >= 0:
                box.blockSignals(True)
                box.setCurrentIndex(index)
                box.blockSignals(False)
        if conv.model and self.model_box.findData(conv.model) < 0:
            conv.model = ""  # the model was removed: keep the one selected
        self._spec = self.services.catalog.get(self.model_box.currentData() or "")
        conv.model = conv.model or (self._spec.id if self._spec else "")
        fields = (self.temperature, self.auto_temperature, self.memory, self.thinking, self.tools,
                  self.instruction)
        for widget in fields:
            widget.blockSignals(True)
        self.auto_temperature.setChecked(conv.temperature is None)
        self.temperature.set_value(0.7 if conv.temperature is None else conv.temperature)
        self.temperature.setEnabled(conv.temperature is not None)
        self.memory.set_value(str(conv.ctx if conv.ctx in MEMORY_OPTIONS else 0))
        self.thinking.setChecked(conv.thinking)
        self.tools.setChecked(conv.tools)
        self.instruction.setPlainText(conv.system)
        for widget in fields:
            widget.blockSignals(False)
        self._rebuild_chips()
        self._render()
        self._refresh_fit()

    def _delete_selected(self) -> None:
        item = self.list.currentItem()
        if item is not None and item.data(Qt.ItemDataRole.UserRole):
            self._delete(item.data(Qt.ItemDataRole.UserRole))

    def _list_menu(self, point: object) -> None:
        item = self.list.itemAt(point)
        if item is None or not item.data(Qt.ItemDataRole.UserRole):
            return
        menu = QMenu(self)
        menu.addAction(icons.icon("trash"), tr("Delete chat"),
                       lambda: self._delete(item.data(Qt.ItemDataRole.UserRole)))
        menu.exec(self.list.viewport().mapToGlobal(point))

    def _delete(self, conv_id: str) -> None:
        conv = self.session.get(conv_id)
        if conv is None:
            return
        answer = QMessageBox.question(self, tr("Delete chat"),
                                      tr("Delete “{title}”? This cannot be undone.", title=conv.title),
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.session.delete(conv_id)
        if conv_id == self._conv.id:
            self.new_chat()

    # ============================================================ messages
    def _render(self) -> None:
        if self._audio_chat != self._conv.id:
            self.audio.clear()
        for view in [*self._views, *([self._live] if self._live is not None else [])]:
            self.thread.removeWidget(view)
            view.hide()  # deleteLater waits for the event loop; the old chat must vanish now
            view.deleteLater()
        self._views, self._live = [], None
        conv = self._conv
        name = self._spec.name if self._spec else ""
        last = len(conv.messages) - 1
        for index, message in enumerate(conv.messages):
            model = self.services.catalog.get(message.model) if message.model else None
            view = MessageView(message, index, model.name if model else message.model, index == last,
                               folder=self._folder())
            view.action.connect(self._message_action)
            view.draw_variant.connect(self._draw_variant)
            view.tool.connect(self._tool_action)
            self.thread.insertWidget(self.thread.count() - 1, view)
            self._views.append(view)
        if self.session.answering == conv.id and self.session.partial is not None:
            self._live = MessageView(self.session.partial, len(conv.messages), name, live=True)
            self.thread.insertWidget(self.thread.count() - 1, self._live)
        self.empty.setVisible(not conv.messages and self._live is None)
        self.heading.setText(conv.title or tr("New chat"))
        self._mark_context()
        self._update_action()
        QTimer.singleShot(0, self._to_bottom)

    def _on_changed(self, conv_id: str) -> None:
        if conv_id == self._conv.id:
            self._render()

    def _on_streaming(self, conv_id: str) -> None:
        partial = self.session.partial
        if conv_id != self._conv.id or partial is None:
            return
        if self._live is None:
            self._render()
        else:
            self._live.update_from(partial, live=True)

    def _follow(self, _low: int, _high: int) -> None:
        """Keep the newest words in sight, unless the user scrolled up to read."""
        if self._sticky:
            self._to_bottom()

    @property
    def _sticky(self) -> bool:
        bar = self.scroll.verticalScrollBar()
        return self._live is not None and bar.maximum() - bar.value() < 160

    def _to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _ctx(self, fit: Fit | None) -> int:
        if fit is not None and isinstance(fit.plan, LlmPlan):
            return fit.plan.ctx
        return self._conv.ctx or DEFAULT_CTX

    def _mark_context(self) -> None:
        """Dim the oldest messages the model no longer sees, and say so."""
        conv = self._conv
        if not conv.messages:
            self.context_note.setVisible(False)
            return
        _sent, dropped = chats.context_messages(conv, self._ctx(self._fit()))
        for view in self._views:
            view.set_out_of_context(view.index < dropped)
        self.context_note.setText(tr("The first {count} messages no longer fit in the model's memory — it "
                                     "does not see them. Start a new chat or choose a longer memory.",
                                     count=dropped))
        self.context_note.setVisible(dropped > 0)

    def _answer_asset(self, text: str) -> Asset:
        return handoff.text(text, self.key, parent=f"chat:{self._conv.id}")

    def _draw_variant(self, text: str) -> None:
        self.send(self._answer_asset(text), "image", "prompt")

    def _message_action(self, name: str, index: int) -> None:
        conv = self._conv
        if not 0 <= index < len(conv.messages):
            return
        if name == "send":
            selection = self._views[index].body.selectedText().replace("\u2029", "\n").replace("\u2028", "\n")
            self.send_menu(self._answer_asset(selection.strip() or conv.messages[index].content))
        elif name == "code":
            self.send(self._answer_asset(conv.messages[index].content), "code", "code_blocks")
        elif name == "read":
            self._read_answer(index)
        elif name == "copy":
            QGuiApplication.clipboard().setText(conv.messages[index].content)
            if self.toasts is not None:
                self.toasts.show(tr("Copied"), "ok", timeout_ms=1500)
        elif name == "edit" and not self.session.busy:
            self._editing = index
            self.text.setPlainText(conv.messages[index].content)
            self.session.pending[conv.id] = conv.messages[index].files
            self._rebuild_chips()
            self.editing_bar.setVisible(True)
            self.text.setFocus()
        elif name == "regenerate" and not self.session.busy:
            if conv.messages[index].role == "assistant":
                del conv.messages[index:]
            self._ask()

    def _cancel_edit(self) -> None:
        self._editing = -1
        self.editing_bar.setVisible(False)
        self.text.clear()
        self.session.pending.pop(self._conv.id, None)  # the files stay with the message they came from
        self._rebuild_chips()

    def _use_idea(self, text: str) -> None:
        self.text.setPlainText(text)
        self.text.setFocus()

    # ============================================================ models
    def _fill_models(self) -> None:
        current = self._spec.id if self._spec else self._conv.model or self.services.settings.recall(
            "chat", "model")
        self.model_box.blockSignals(True)
        self.model_box.clear()
        for spec in self.services.catalog.all("chat"):
            name = spec.name
            if not self.services.installed(spec):
                name += "  ·  " + size_text(chat_download_gb(spec, self.services.fit(spec)))
            self.model_box.addItem(name, spec.id)
        self.model_box.setCurrentIndex(max(0, self.model_box.findData(current)))
        self.model_box.blockSignals(False)
        self._spec = self.services.catalog.get(self.model_box.currentData() or "")
        self._refresh_fit()

    def select_model(self, model_id: str) -> None:
        index = self.model_box.findData(model_id)
        if index >= 0:
            self.model_box.setCurrentIndex(index)

    def _model_selected(self, _index: int) -> None:
        self._spec = self.services.catalog.get(self.model_box.currentData() or "")
        self._conv.model = self._spec.id if self._spec else ""
        self._save_settings_of_chat()
        self._refresh_fit()

    def _role_selected(self, _index: int) -> None:
        self._conv.role = self.role_box.currentData() or chats.DEFAULT_ROLE
        self._save_settings_of_chat()

    def _params_changed(self, *_args: object) -> None:
        conv = self._conv
        auto = self.auto_temperature.isChecked()
        self.temperature.setEnabled(not auto)
        conv.temperature = None if auto else self.temperature.value()
        conv.thinking = self.thinking.isChecked()
        conv.tools = self.tools.isChecked()
        conv.ctx = int(self.memory.value() or 0)
        conv.system = self.instruction.toPlainText()
        self._save_settings_of_chat()
        self._refresh_fit()

    def _save_settings_of_chat(self) -> None:
        if self.session.get(self._conv.id) is not None and self.session.answering != self._conv.id:
            self.session.store.save(self._conv)  # settings are not news: the chat keeps its place

    def _fit(self) -> Fit | None:
        return self.services.fit(self._spec, ctx=self._conv.ctx) if self._spec else None

    def _reasoning(self) -> bool:
        return self._spec is not None and "reasoning" in self._spec.capabilities

    def _refresh_fit(self) -> None:
        self.thinking.setVisible(self._reasoning())
        self.tools.setVisible(self._can_use_tools())
        self.fit_banner.set_fit(self._fit())
        self._mark_context()
        self._update_action()

    def _on_hardware(self, _hw: object) -> None:
        self._fill_models()

    # ============================================================ sending
    def _missing(self) -> list[ModelSpec]:
        """What has to be downloaded first: the server for this computer and the model."""
        out = []
        engine = self.services.chat_runtime()
        if engine is not None and not self.services.installed(engine):
            out.append(engine)
        if self._spec is not None and not self.services.installed(self._spec):
            out.append(self._spec)
        return out

    def _update_action(self) -> None:
        session, spec = self.session, self._spec
        self._text_changed_counter()
        answering_here = session.answering == self._conv.id
        if answering_here:
            self.action.setText(tr("Stop"))
            self.action.setEnabled(True)
            self.status.setText(tr("Loading the model…") if session.loading else tr("Writing…"))
            return
        self.status.setText(tr("Answering in another chat…") if session.busy else "")
        if self.services.hardware is None:
            self._set_action(tr("Checking this computer…"), False)
            return
        if spec is None:
            self._set_action(tr("Send"), False)
            self.status.setText(tr("No chat models yet: add one on the Models page."))
            return
        engine = self.services.chat_runtime()
        if engine is None:
            self._set_action(tr("Send"), False)
            self.status.setText(tr("Chat is not available for this computer yet."))
            return
        active = [s for s in (engine, spec) if self.services.downloads.is_active(s.id)]
        if active:
            done = total = 0
            for item in active:
                state = self.services.downloads.state(item.id)
                if state:
                    done, total = done + state[0], total + state[1]
            percent = f" {round(done / total * 100)} %" if total else ""
            self._set_action(tr("Downloading") + percent, False)
            return
        missing = self._missing()
        fit = self._fit()
        if missing:
            size = sum(chat_download_gb(s, fit) if s is spec else s.download_gb for s in missing)
            self._set_action(tr("Download ({size})", size=size_text(size)), fit is None or fit.verdict != NO)
            return
        blind = any(a.images for a in self._pending()) and not self._sees()
        if blind:
            self.status.setText(tr("This model does not see pictures. Choose a model marked “sees images” "
                                   "or remove the pictures."))
        elif self._reading:
            self.status.setText(tr("Reading the files…"))
        ready = bool(self.text.toPlainText().strip() or self._pending()) and not self._reading and not blind
        self._set_action(tr("Send"), ready and not session.busy and (fit is None or fit.verdict != NO))

    def _set_action(self, text: str, enabled: bool) -> None:
        self.action.setText(text)
        self.action.setEnabled(enabled)

    def _action_clicked(self) -> None:
        if self.session.answering == self._conv.id:
            self.session.stop()
            return
        missing = self._missing()
        if missing:
            self._download(missing)
            return
        self.generate()

    def _download(self, missing: list[ModelSpec]) -> None:
        for spec in missing:
            if spec.kind == "chat" and spec.source == "hf":
                files = chat_download_files(spec, self.services.fit(spec))
                if files:
                    self.services.downloads.start(spec, files)
            else:
                self.services.downloads.start(spec)
        self._update_action()

    def generate(self) -> None:
        text = self.text.toPlainText().strip()
        files = self._pending()
        if not (text or files) or not self.action.isEnabled() or self.session.busy or self._missing():
            return
        conv = self._conv
        if self._editing >= 0:
            del conv.messages[self._editing:]
            self._editing = -1
            self.editing_bar.setVisible(False)
        conv.messages.append(Message("user", text, attachments=[a.to_dict() for a in files]))
        self.session.pending.pop(conv.id, None)
        self.text.clear()
        self._remember_draft()
        self._rebuild_chips()
        self._ask()

    def _ask(self) -> None:
        """Send the conversation as it is (its last message is the user's)."""
        conv, spec, fit = self._conv, self._spec, self._fit()
        if spec is None or fit is None or not isinstance(fit.plan, LlmPlan) or not conv.messages:
            return
        launch = self.services.chat_launch(spec, ctx=conv.ctx)
        if launch is None:
            if self.toasts is not None:
                self.toasts.show(messages.engine_error("not_installed"), "bad")
            return
        self.session.send(conv, launch, fit.plan.ctx, self._reasoning(), conv.tools and self._can_use_tools())
        self._remember()
        self._render()

    def cancel(self) -> None:
        if self.session.answering == self._conv.id:
            self.session.stop()
            return
        for spec in self._missing():
            if self.services.downloads.is_active(spec.id):
                self.services.downloads.cancel(spec.id)

    def _on_failed(self, conv_id: str, code: str, _detail: str) -> None:
        if self.toasts is not None:
            self.toasts.show(messages.llm_error(code), "bad")

    def _on_download_failed(self, model_id: str, code: str, _message: str) -> None:
        self._update_action()
        ours = {s.id for s in (self._spec, self.services.chat_runtime()) if s is not None}
        if model_id in ours and self.toasts is not None:
            self.toasts.show(messages.hub_error(code), "bad")

    # ============================================================ input
    def _text_changed(self) -> None:
        self._update_action()

    def _text_changed_counter(self) -> None:
        """About how much of the model's memory the conversation and the new message take."""
        conv = self._conv
        files = self._pending()
        if not conv.messages and not self.text.toPlainText().strip() and not files:
            self.counter.setText("")
            return
        used = chats.estimate_tokens(conv.instruction) + chats.estimate_tokens(self.text.toPlainText())
        used += sum(m.tokens() for m in conv.messages) + sum(a.tokens for a in files)
        self.counter.setText(tr("~{used} / {total} tokens", used=f"{used:,}".replace(",", " "),
                                total=f"{self._ctx(self._fit()):,}".replace(",", " ")))

    # ============================================================ works the model proposes
    def _can_use_tools(self) -> bool:
        return self._spec is not None and "tools" in self._spec.capabilities

    def _read_answer(self, index: int) -> None:
        message = self._conv.messages[index]
        text = QTextDocumentFragment.fromHtml(self._views[index].body.text()).toPlainText().strip()
        if message.role != "assistant" or not text:
            return
        for number, tool in enumerate(message.tools):
            if tool.get("answer_audio"):
                paths = tool.get("paths", [])
                if paths and Path(paths[0]).is_file():
                    self._play_audio(paths[0])
                elif tool["status"] != "running":
                    self._tool_action("create", index, number)
                return
        message.tools.append({"name": "speak", "value": text, "status": "proposed",
                              "answer_audio": True, "paths": []})
        self._tool_action("create", index, len(message.tools) - 1)

    def _play_audio(self, path: str) -> None:
        self._audio_chat = self._conv.id
        self.audio.play(path)

    def _on_audio_failed(self, detail: str) -> None:
        if self.toasts is not None:
            self.toasts.show(tr("Could not play the audio.") + (" " + detail if detail else ""), "warn")

    def hideEvent(self, event: QHideEvent) -> None:
        self.audio.clear()
        super().hideEvent(event)

    def _tool_action(self, action: str, message: int, number: int) -> None:
        """A button on a card under an answer. Nothing is created without "Create"."""
        conv = self._conv
        if not 0 <= message < len(conv.messages) or not 0 <= number < len(conv.messages[message].tools):
            return
        tool = conv.messages[message].tools[number]
        if action == "create" and tool["status"] == "running":
            return
        page_key, role = TOOL_ROUTES.get(tool["name"], ("", ""))
        window = self.window()
        target = window.page(page_key) if hasattr(window, "page") else None
        asset = handoff.text(tool["value"], "chat", parent=f"chat:{conv.id}:{message}:{number}")
        if action == "play" and tool.get("paths"):
            self._play_audio(tool["paths"][0])
            return
        if action == "cancel":
            for job_id, (_, pending) in self.services.chat_speech_jobs.items():
                if pending is tool:
                    self.services.worker.cancel(job_id)
                    break
            return
        if action == "create" and isinstance(target, SpeechPage):
            job = target.chat_job(tool["value"], asset.parent)
            if job is None:
                window.send(asset, Route(page_key, role, ""))
                tool["status"] = "sent"
            else:
                tool.update(status="running", paths=[], chat_speech=True)
                self.services.chat_speech_jobs[job.id] = (conv.id, tool)
                self.services.worker.submit(job)
        elif action == "create" and target is not None:
            target.receive(asset, role)
            queued = len(getattr(target, "_jobs", ()))
            target.generate()  # with that section's model and settings
            if len(getattr(target, "_jobs", ())) > queued or getattr(target, "_translating", False):
                tool["status"] = "running"
            else:  # the model there is not downloaded, or something is missing: let the user see
                window.send(asset, Route(page_key, role, ""))
                tool["status"] = "sent"
        elif action == "edit" and target is not None:
            window.send(asset, Route(page_key, role, ""))
            tool["status"] = "sent"
        elif action == "decline":
            tool["status"] = "declined"
        elif action == "show" and target is not None:
            window.open_page(window.pages.index(target))
            return
        elif action in ("open", "send") and tool.get("paths"):
            path = tool["paths"][0]
            if action == "open":
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                found = handoff.from_path(path, "chat")
                if found is not None:
                    self.send_menu(found)
            return
        self.session.store.save(conv)
        self._render()

    def _on_speech_failed(self, job_id: int, code: str, detail: str) -> None:
        if self._finish_chat_speech(job_id) and self.toasts is not None:
            self.toasts.show(messages.engine_error(code, detail), "bad")

    def _finish_chat_speech(self, job_id: int, paths: list[str] | None = None) -> bool:
        request = self.services.chat_speech_jobs.pop(job_id, None)
        if request is None:
            return False
        conv_id, tool = request
        conv = self.session.get(conv_id)
        if conv is None or not any(card is tool for message in conv.messages for card in message.tools):
            return True  # the answer was replaced while the job was running
        tool.update(status="done" if paths else "failed", paths=paths or [])
        self.session.store.save(conv)
        if conv_id == self._conv.id:
            self._render()
            if paths and tool.get("answer_audio") and self.isVisible():
                self._play_audio(paths[0])
        return True

    def _on_job_finished(self, job_id: int, results: list) -> None:
        """A work the model proposed is ready: it appears on its card."""
        if self._finish_chat_speech(job_id, [result["path"] for result in results if result.get("path")]):
            return
        changed = set()
        for result in results:
            parts = str(result.get("params", {}).get("parent", "")).split(":")
            if len(parts) != 4 or parts[0] != "chat":
                continue
            conv = self.session.get(parts[1])
            try:
                tool = conv.messages[int(parts[2])].tools[int(parts[3])] if conv else None
            except (IndexError, ValueError):
                tool = None
            if tool is not None:
                tool["status"] = "done"
                tool.setdefault("paths", []).append(result.get("path", ""))
                changed.add(conv.id)
        for conv_id in changed:
            conv = self.session.get(conv_id)
            if conv is not None:
                self.session.store.save(conv)
            if conv_id == self._conv.id:
                self._render()

    # ============================================================ handoff (gui/handoff.py)
    def routes(self, asset: Asset) -> list[Route]:
        if asset.kind == "video" and asset.path:
            return [
                Route("chat", "attachment", tr("Ask about it in the chat")),
                Route("chat", "describe_video", tr("Describe the video")),
                Route("chat", "narrate_video", tr("Write narration for the video")),
            ]
        if asset.kind in ("image", "audio") and asset.path:
            return [Route("chat", "attachment", tr("Ask about it in the chat"))]
        if asset.kind == "text" and asset.text.strip() and asset.source != "chat":
            return [Route("chat", "text", tr("Discuss in the chat"))]
        return []

    def receive(self, asset: Asset, role: str) -> None:
        instructions = {
            "describe_video": tr("Describe what happens in the attached video in chronological order. "
                                 "Reply with text only and do not call tools."),
            "narrate_video": tr("Write a short narration script for the attached video, "
                                "following the action. Reply with the script only and do not call tools."),
        }
        if role == "attachment" or role in instructions:
            self.add_files([Path(asset.path)], text_only=role in instructions)
            if role in instructions:
                draft = self.text.toPlainText()
                instruction = instructions[role]
                self.text.setPlainText(f"{draft}\n\n{instruction}" if draft.strip() else instruction)
        elif role == "text":
            self.text.setPlainText(asset.text.strip())
        self.text.setFocus()

    # ============================================================ attachments
    def _folder(self) -> Path:
        return self.session.store.files_dir(self._conv.id)

    def _pending(self) -> list[Attachment]:
        return self.session.pending.get(self._conv.id, [])

    def _sees(self) -> bool:
        """Whether the selected model can look at pictures (it needs its projector on disk)."""
        spec = self._spec
        if spec is None or "vision" not in spec.capabilities:
            return False
        return not self.services.installed(spec) or self.services.store.chat_files(spec)[1] is not None

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, tr("Attach files"))
        self.add_files([Path(f) for f in files])

    def add_files(self, files: list[Path], *, text_only: bool = False) -> None:
        folder = self._folder()
        for file in files:
            self._read(file.name, lambda f=file: attachments.prepare(f, folder, self._transcribe),
                       text_only=text_only)

    def _transcribe(self, audio: Path) -> str | None:
        """Speech in an attachment, in the reading thread; None when no recognition model is installed."""
        started = self.services.transcribe(audio)
        return started[1].result() if started is not None else None

    def _add_image(self, image: QImage) -> None:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        data, folder, name = bytes(buffer.data()), self._folder(), tr("Pasted picture")

        def prepare() -> Attachment:
            import io

            from PIL import Image

            with Image.open(io.BytesIO(data)) as picture:
                return attachments.image_attachment(picture.copy(), folder, name + ".png")

        self._read(name, prepare)

    def _read(self, name: str, prepare: Callable[[], Attachment], *, text_only: bool = False) -> None:
        """Read a file in the background; its chip shows progress, then what the model gets."""
        conv_id = self._conv.id
        chip = AttachmentChip(name)
        chip.removed.connect(self._remove_chip)
        self._show_chip(chip)
        self._reading += 1
        self._update_action()

        def done(item: Attachment) -> None:
            self._reading -= 1
            item.text_only = text_only
            self.session.pending.setdefault(conv_id, []).append(item)
            if conv_id == self._conv.id and chip in self._chips:
                chip.set_item(item, self._folder())
            elif chip in self._chips:
                self._drop_chip(chip)
            self._update_action()

        def failed(exc: object) -> None:
            self._reading -= 1
            if chip in self._chips:
                self._drop_chip(chip)
            code = exc.code if isinstance(exc, AttachmentError) else "unreadable"
            if self.toasts is not None:
                self.toasts.show(messages.attachment_error(code, name), "warn")
            self._update_action()

        run_async(prepare, done, failed)

    def _show_chip(self, chip: AttachmentChip) -> None:
        self._chips.append(chip)
        self.chips_row.insertWidget(self.chips_row.count() - 1, chip)
        self.chips.setVisible(True)

    def _drop_chip(self, chip: AttachmentChip) -> None:
        self._chips.remove(chip)
        self.chips_row.removeWidget(chip)
        chip.hide()
        chip.deleteLater()
        self.chips.setVisible(bool(self._chips))

    def _rebuild_chips(self) -> None:
        for chip in list(self._chips):
            if chip.item is not None:  # files still being read keep their chips
                self._drop_chip(chip)
        for item in self._pending():
            chip = AttachmentChip(item.name, item, self._folder())
            chip.removed.connect(self._remove_chip)
            self._show_chip(chip)

    def _remove_chip(self, chip: AttachmentChip) -> None:
        item = chip.item
        self._drop_chip(chip)
        pending = self._pending()
        if item is not None and item in pending:
            pending.remove(item)
            used = {f for m in self._conv.messages for a in m.files for f in a.files}
            for name in item.files:  # still in an earlier message: keep it
                if name not in used:
                    (self._folder() / name).unlink(missing_ok=True)
        self._update_action()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if local_files(event.mimeData()):
            event.acceptProposedAction()
            self._set_dropping(True)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_dropping(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_dropping(False)
        files = local_files(event.mimeData())
        if files:
            event.acceptProposedAction()
            self.add_files(files)

    def _set_dropping(self, on: bool) -> None:
        self.setProperty("dropping", on)
        self.style().unpolish(self)
        self.style().polish(self)

    # ============================================================ persistence
    def shown(self) -> None:
        self._refresh_fit()

    def save_state(self) -> None:
        if self._storyboard is not None:
            self._storyboard.detach()
        self._remember()

    def _drafts(self) -> dict[str, str]:
        drafts = self.services.settings.recall("chat", "drafts", {})
        return drafts if isinstance(drafts, dict) else {}

    def _remember_draft(self) -> None:
        """What was typed in each chat but not sent; chats that no longer exist are forgotten."""
        drafts = {k: v for k, v in self._drafts().items() if v and self.session.get(k) is not None}
        drafts.pop(self._conv.id, None)
        if self.text.toPlainText().strip():
            drafts[self._conv.id] = self.text.toPlainText()
        self.services.settings.remember("chat", drafts=drafts)

    def _remember(self) -> None:
        self._remember_draft()
        self.services.settings.remember("chat", chat=self._conv.id, model=self._spec.id if self._spec else "",
                                        role=self._conv.role)

    def _restore(self) -> None:
        recall = self.services.settings.recall
        conv = self.session.get(recall("chat", "chat", "") or "")
        if conv is not None:
            self._conv = conv
        else:  # a new chat that has no messages yet: same id, so its draft is found
            self._conv = Conversation(id=recall("chat", "chat", "") or "",
                                      model=recall("chat", "model", "") or "",
                                      role=recall("chat", "role", chats.DEFAULT_ROLE))
        self.text.setPlainText(self._drafts().get(self._conv.id, ""))
        self._apply_conversation()
        self._fill_list()
