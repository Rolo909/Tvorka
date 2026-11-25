"""One message of a chat: the text (Markdown for answers), folded reasoning and actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QFontMetrics,
    QResizeEvent,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from tvorka.core.chats import Message
from tvorka.gui import icons, theme
from tvorka.gui.widgets.basic import Disclosure, label, tool_button
from tvorka.gui.widgets.canvas import load_scaled
from tvorka.gui.widgets.chat_attachments import AttachmentChip
from tvorka.i18n import tr


def markdown_html(text: str) -> str:
    """Markdown as HTML in the theme's colours: thin table borders, code in the mono font."""
    document = QTextDocument()
    document.setMarkdown(text)
    line, code_bg = theme.color("line"), theme.color("raised")
    block = document.begin()
    while block.isValid():
        table = QTextCursor(block).currentTable()
        if table is not None:
            fmt = table.format()
            if fmt.borderBrush().color() != line:
                fmt.setBorderBrush(line)
                fmt.setBorder(1)
                fmt.setBorderCollapse(True)
                fmt.setCellPadding(4)
                table.setFormat(fmt)
        if block.blockFormat().hasProperty(QTextFormat.Property.BlockCodeFence):
            cursor = QTextCursor(block)
            block_format = block.blockFormat()
            block_format.setBackground(code_bg)
            cursor.setBlockFormat(block_format)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            mono = QTextCharFormat()
            mono.setFontFamilies([theme.font_family("mono")])
            cursor.mergeCharFormat(mono)
        block = block.next()
    return document.toHtml()


def _text(role: str) -> QLabel:
    widget = label("", "chat", wrap=True)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                   | Qt.TextInteractionFlag.LinksAccessibleByMouse)
    widget.setOpenExternalLinks(True)
    # Answers are Markdown; what the user typed is shown exactly as typed.
    widget.setTextFormat(Qt.TextFormat.RichText if role == "assistant" else Qt.TextFormat.PlainText)
    return widget


def _numbered_items(text: str) -> list[str]:
    """Text of top-level Markdown ordered lists with multiple items."""
    document = QTextDocument()
    document.setMarkdown(text)
    items: list[list[str]] = []
    current: list[str] | None = None
    block = document.begin()
    while block.isValid():
        text_list = block.textList()
        if text_list is not None and text_list.format().indent() == 1:
            current = None
            if text_list.format().style() == QTextListFormat.Style.ListDecimal and text_list.count() > 1:
                current = []
                items.append(current)
        elif text_list is None and block.blockFormat().indent() == 0:
            current = None
        text = block.text().strip()
        if current is not None and text:
            current.append(text)
        block = block.next()
    return ["\n".join(item) for item in items if item]


class MessageView(QWidget):
    """``action`` carries ``copy``, ``edit`` or ``regenerate`` for the message at ``index``."""

    action = Signal(str, int)
    draw_variant = Signal(str)
    tool = Signal(str, int, int)  # create | edit | decline | show | open | send, message index, tool index

    def __init__(self, message: Message, index: int, model_name: str = "", last: bool = False,
                 live: bool = False, folder: Path | None = None, full_width: bool = False) -> None:
        super().__init__()
        self.index, self.role = index, message.role
        self._full_width = full_width
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.bubble = QFrame()
        self.bubble.setObjectName("ChatBubble")
        self.bubble.setProperty("who", message.role)
        box = QVBoxLayout(self.bubble)
        if message.role == "user":
            box.setContentsMargins(14, 10, 14, 8)
        else:
            box.setContentsMargins(2, 4, 2, 4)
        box.setSpacing(6)
        if message.role == "user" and not full_width:
            outer.addStretch(1)  # the user's messages sit on the right, as wide as their text
        outer.addWidget(self.bubble)

        self.reasoning = Disclosure(tr("Reasoning"))
        self.reasoning_text = label("", "faint", wrap=True)
        self.reasoning_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reasoning.body.addWidget(self.reasoning_text)
        box.addWidget(self.reasoning)
        self.body = _text(message.role)
        box.addWidget(self.body)
        if message.role == "assistant" and not live:
            items = _numbered_items(message.content)
            if items:
                box.addWidget(self._variants(items))
        if message.attachments:  # the files that went with the message
            files = QHBoxLayout()
            files.setSpacing(6)
            if message.role == "user":
                files.addStretch(1)
            for item in message.files:
                files.addWidget(AttachmentChip(item.name, item, folder, removable=False))
            if message.role != "user":
                files.addStretch(1)
            box.addLayout(files)
        self.note = label("", "faint", wrap=True)
        box.addWidget(self.note)
        for number, tool in enumerate(message.tools):  # what the model proposes to create
            box.addWidget(ToolCard(self, number, tool))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        if message.role == "user":
            row.addStretch(1)
        self.meta = label("", "faint")
        buttons = [("copy", "copy", tr("Copy"))]
        if message.role == "user":
            buttons.append(("edit", "edit", tr("Edit and send again")))
        else:
            buttons.append(("send", "link", tr("Send to… (draw it, make a video, read aloud)")))
            if not live and "```" in message.content:
                buttons.append(("code", "code", tr("Open in Code")))
            if message.content.strip() and not live:
                buttons.append(("read", "voice", tr("Read answer aloud")))
            if last:
                buttons.append(("regenerate", "refresh", tr("Answer again")))
        self.buttons = []
        for name, glyph, tip in buttons:
            button = tool_button(glyph, tip)
            button.clicked.connect(lambda _=False, n=name: self.action.emit(n, self.index))
            row.addWidget(button)
            self.buttons.append(button)
        row.addWidget(self.meta)
        if message.role != "user":
            row.addStretch(1)
        self.actions = QWidget()
        self.actions.setLayout(row)
        box.addWidget(self.actions)
        self.model_name = model_name
        self.update_from(message, live)

    def _variants(self, items: list[str]) -> Disclosure:
        panel = Disclosure(tr("Prompt variants"))
        for text in items:
            row = QHBoxLayout()
            prompt = label(text, "", wrap=True)
            prompt.setTextFormat(Qt.TextFormat.PlainText)
            row.addWidget(prompt, 1)
            draw = QPushButton(tr("Draw this"))
            draw.setProperty("role", "ghost")
            draw.clicked.connect(lambda _checked=False, variant=text: self.draw_variant.emit(variant))
            row.addWidget(draw)
            panel.body.addLayout(row)
        return panel

    def resizeEvent(self, event: QResizeEvent) -> None:
        """A user's message is as wide as its text, at most three quarters of the conversation."""
        super().resizeEvent(event)
        if self.role != "user" or self._full_width:
            return
        widest = int(self.width() * 0.75)
        metrics = QFontMetrics(self.body.font())
        text = max((metrics.horizontalAdvance(line) for line in self.body.text().splitlines()), default=0)
        inner = min(widest - 28, max(text + 4, 120))  # 28: the bubble's side padding
        if self.body.minimumWidth() != inner:
            self.body.setMinimumWidth(inner)
            self.bubble.setMaximumWidth(widest)

    def update_from(self, message: Message, live: bool = False) -> None:
        """Show ``message``; ``live`` while its answer is still being written."""
        self.reasoning.setVisible(bool(message.reasoning))
        self.reasoning.toggle.setText(tr("Thinking…") if live and not message.content else tr("Reasoning"))
        self.reasoning_text.setText(message.reasoning.strip())
        self.body.setText(markdown_html(message.content) if self.role == "assistant" else message.content)
        self.body.setVisible(bool(message.content))
        notes = []
        if message.stopped:
            notes.append(tr("The answer was cut short."))
        self.note.setText(" ".join(notes))
        self.note.setVisible(bool(notes))
        self.actions.setVisible(not live)
        meta = [self.model_name] if message.role == "assistant" and self.model_name else []
        speed = message.stats.get("predicted_per_second")
        if speed:
            meta.append(tr("{speed:.0f} tokens/s", speed=float(speed)))
        self.meta.setText("  ·  ".join(meta))

    def set_out_of_context(self, out: bool) -> None:
        """Older messages the model no longer sees are dimmed."""
        self.body.setProperty("role", "faint" if out else "chat")
        self.body.style().unpolish(self.body)
        self.body.style().polish(self.body)
        self.setToolTip(tr("The model no longer sees this message: the conversation is longer than "
                           "its memory.") if out else "")


TOOL_TITLES = {"generate_image": "image", "generate_video": "video", "speak": "voice"}


class ToolCard(QFrame):
    """What the model proposes to create; nothing runs until the user presses "Create"."""

    def __init__(self, view: MessageView, index: int, tool: dict) -> None:
        super().__init__()
        self.setObjectName("Banner")
        name, status = tool.get("name", ""), tool.get("status", "")
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 10, 12, 10)
        box.setSpacing(6)
        titles = {"generate_image": tr("The model suggests creating a picture"),
                  "generate_video": tr("The model suggests creating a video clip"),
                  "speak": tr("The model suggests reading this aloud")}
        head = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(icons.pixmap(TOOL_TITLES.get(name, "chat"), 16, "accent_text"))
        head.addWidget(icon)
        title = tr("Answer audio") if tool.get("answer_audio") else titles.get(name, name)
        head.addWidget(label(title, "heading"), 1)
        box.addLayout(head)
        if not tool.get("answer_audio"):
            value = label(tool.get("value", ""), "", wrap=True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(value)
        row = QHBoxLayout()
        row.setSpacing(6)

        def button(text: str, action: str, role: str = "ghost") -> None:
            widget = QPushButton(text)
            widget.setProperty("role", role)
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            widget.clicked.connect(lambda: view.tool.emit(action, view.index, index))
            row.addWidget(widget)

        paths = [p for p in tool.get("paths", []) if p]
        if status == "proposed":
            button(tr("Create"), "create", "accent")
            button(tr("Edit first"), "edit")
            button(tr("Cancel"), "decline")
        elif status == "running":
            row.addWidget(label(tr("Being created…"), "muted"))
            if tool.get("chat_speech"):
                button(tr("Cancel"), "cancel")
            else:
                button(tr("Open the section"), "show")
        elif status == "done" and paths:
            if name == "generate_image":
                preview = QLabel()
                preview.setPixmap(load_scaled(paths[0], 280))
                box.addWidget(preview)
            else:
                box.addWidget(label(Path(paths[0]).name, "mono"))
            if name == "speak":
                button(tr("Play"), "play")
            button(tr("Open"), "open")
            button(tr("Send to…"), "send")
        elif status == "failed" and name == "speak":
            row.addWidget(label(tr("Speech synthesis did not finish."), "warn"))
            button(tr("Create"), "create")
        else:
            notes = {"declined": tr("Cancelled."), "sent": tr("Handed over to the section to edit."),
                     "invalid": tr("The model made a broken request. Ask again in other words.")}
            row.addWidget(label(notes.get(status, ""), "faint"))
        row.addStretch(1)
        box.addLayout(row)
