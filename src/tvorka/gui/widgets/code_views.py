"""The code page's project tree, source preview and approval card."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from tvorka.core.code.tools import Approval
from tvorka.gui import theme
from tvorka.gui.widgets.basic import label
from tvorka.i18n import tr

_PATH = Qt.ItemDataRole.UserRole


class FileTree(QTreeWidget):
    file_opened = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._files: dict[str, QTreeWidgetItem] = {}
        self.setHeaderHidden(True)
        self.setAccessibleName(tr("Project files"))
        self.itemDoubleClicked.connect(self._open)

    def fill(self, files: list[str], selected: set[str]) -> None:
        self.clear()
        root = self.invisibleRootItem()
        folders: dict[str, QTreeWidgetItem] = {"": root}
        for path in files:
            if path.startswith("…"):
                continue
            parts = PurePosixPath(path).parts
            parent = root
            for index, part in enumerate(parts[:-1]):
                key = "/".join(parts[:index + 1])
                if key not in folders:
                    folders[key] = QTreeWidgetItem(parent, [part])
                parent = folders[key]
            item = QTreeWidgetItem(parent, [parts[-1]])
            item.setData(0, _PATH, path)
            item.setToolTip(0, path)
            item.setCheckState(0, Qt.CheckState.Checked if path in selected else Qt.CheckState.Unchecked)
            self._files[path] = item
        self.expandToDepth(0)

    def clear(self) -> None:
        self._files.clear()
        super().clear()

    def checked(self) -> tuple[str, ...]:
        return tuple(sorted(path for path, item in self._files.items()
                            if item.checkState(0) == Qt.CheckState.Checked))

    def mark(self, path: str) -> None:
        if item := self._files.get(path):
            item.setCheckState(0, Qt.CheckState.Checked)

    def _open(self, item: QTreeWidgetItem, _column: int) -> None:
        if path := item.data(0, _PATH):
            self.file_opened.emit(path)


class CodeHighlight(QSyntaxHighlighter):
    _patterns = (
        (re.compile(r"\b(?:def|class|from|import|return|async|await|if|else|for|in|while|try|except|"
                    r"const|let|var|function|export|interface|new|true|false|null|True|False|None)\b|</?\w+"),
         "accent"),
        (re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'"), "ok"),
        (re.compile(r"(?:^\s*#|//|<!--|/\*).*$"), "muted"),
    )

    def __init__(self, editor: QPlainTextEdit, *, diff: bool = False) -> None:
        super().__init__(editor.document())
        self.diff = diff

    def _color(self, start: int, length: int, token: str) -> None:
        pattern = QTextCharFormat()
        pattern.setForeground(theme.color(token))
        self.setFormat(start, length, pattern)

    def highlightBlock(self, text: str) -> None:
        if self.diff:
            if text.startswith(("+", "-", "@@")):
                token = "ok" if text.startswith("+") else "bad" if text.startswith("-") else "accent"
                self._color(0, len(text), token)
            return
        for pattern, token in self._patterns:
            for match in pattern.finditer(text):
                self._color(match.start(), len(match[0]), token)


def preview(title: str) -> QPlainTextEdit:
    field = QPlainTextEdit()
    field.setAccessibleName(title)
    field.setReadOnly(True)
    field.setFont(theme.font("mono", 9))
    field.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    return field


class ApprovalCard(QFrame):
    decided = Signal(int, str, str)

    def __init__(self, identifier: int, approval: Approval) -> None:
        super().__init__()
        self.setObjectName("Composer")
        self.identifier, self.approval = identifier, approval
        command = approval.kind in {"command", "dangerous"}
        box = QVBoxLayout(self)
        title = {"write": tr("Proposed change"), "delete": tr("Delete file"),
                 "image": tr("Create image asset"),
                 "command": tr("Run this command?"), "dangerous": tr("Command requires careful review")}
        box.addWidget(label(title[approval.kind], "warn" if approval.kind == "dangerous" else "heading"))
        if command:
            details = preview(title[approval.kind])
            details.setPlainText(approval.label)
            details.setFixedHeight(74)
            box.addWidget(details)
            box.addWidget(label(tr("Timeout: {seconds} s", seconds=approval.detail), "faint"))
        else:
            text = label(approval.label, "mono", wrap=True)
            text.setTextFormat(Qt.TextFormat.PlainText)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box.addWidget(text)
        self.note = QLineEdit()
        self.note.setPlaceholderText(tr("Optional reason for declining"))
        box.addWidget(self.note)
        row = QHBoxLayout()
        apply = QPushButton(tr("Run command") if command else tr("Apply"))
        apply.setProperty("role", "accent")
        apply.clicked.connect(self._apply)
        row.addWidget(apply)
        decline = QPushButton(tr("Decline"))
        decline.clicked.connect(self._reject)
        row.addWidget(decline)
        box.addLayout(row)
        if approval.allow_session:
            remember = tr("Allow in this session") if command else tr("Auto-apply in this session")
            session = QPushButton(remember)
            session.clicked.connect(self._allow)
            box.addWidget(session)

    def _apply(self) -> None:
        self.decided.emit(self.identifier, "apply", "")

    def _allow(self) -> None:
        action = "allow_session" if self.approval.kind == "command" else "apply_all_session"
        self.decided.emit(self.identifier, action, "")

    def _reject(self) -> None:
        self.decided.emit(self.identifier, "reject", self.note.text())
