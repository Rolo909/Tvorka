"""The local project workspace in Tvorka."""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tvorka.core import advisor, paths
from tvorka.core.catalog import ModelSpec
from tvorka.core.chats import Message
from tvorka.core.code.agent import Event
from tvorka.core.code.commands import git_status
from tvorka.core.code.edit_blocks import code_files
from tvorka.core.code.tools import Approval
from tvorka.core.code.workspace import Workspace, WorkspaceError
from tvorka.gui import handoff
from tvorka.gui.handoff import Asset, Route
from tvorka.gui.pages.base import Page
from tvorka.gui.services import Services
from tvorka.gui.widgets.basic import Disclosure, Segmented, label
from tvorka.gui.widgets.chat_attachments import ComposerEdit
from tvorka.gui.widgets.chat_message import MessageView
from tvorka.gui.widgets.code_views import ApprovalCard, CodeHighlight, FileTree, preview
from tvorka.gui.widgets.feedback import ToastHost
from tvorka.gui.widgets.mic import MicButton
from tvorka.i18n import messages, tr
from tvorka.workers.code_agent import Request
from tvorka.workers.downloads import run_async

CONTEXTS = (8192, 16384, 32768)
_TEMPLATES = {"empty": (), "web": ("index.html", "style.css", "script.js"),
              "python": ("main.py", "README.md")}


class CodePage(Page):
    key = icon = "code"

    def __init__(self, services: Services, toasts: ToastHost | None) -> None:
        super().__init__(services, toasts)
        self.worker = services.code
        self.workspace: Workspace | None = None
        self._recent: list[str] = services.settings.recall(self.key, "recent", []) or []
        self._current_file = ""
        self._stream = Message("assistant")
        self._live: MessageView | None = None
        self._approval: ApprovalCard | None = None
        self._tool: Disclosure | None = None
        self._context = 0
        self._model_ready = False
        self._files_token = 0
        self._files_loading = False
        self._preferred_model = str(services.settings.recall(self.key, "model", ""))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setChildrenCollapsible(False)
        self.split.addWidget(self._project_panel())
        self.split.addWidget(self._conversation_panel())
        self.split.addWidget(self._inspector())
        self.split.setStretchFactor(1, 2)
        self.split.setStretchFactor(2, 1)
        self.split.setSizes(services.settings.recall(self.key, "split", [190, 480, 280]))
        outer.addWidget(self.split)

        services.models_changed.connect(self._models)
        services.hardware_ready.connect(self._models)
        self.worker.event_added.connect(self._event)
        self.worker.delta.connect(self._delta)
        self.worker.approval_needed.connect(self._approve)
        self.worker.failed.connect(self._failed)
        self.worker.settled.connect(self._settled)
        self.worker.finished.connect(self._update)
        self._models()
        saved = self.worker.request.workspace.root if self.worker.isRunning() and self.worker.request else (
            services.settings.recall(self.key, "project", ""))
        if saved and Path(saved).is_dir():
            selected = set(services.settings.recall(self.key, "selected", []) or [])
            self.open_project(Path(saved), selected)
        if self.worker.isRunning():
            for event in list(self.worker.events):
                self._event(event)
            if self.worker.partial:
                self._delta(self.worker.partial, "")
            if self.worker.pending:
                self._approve(*self.worker.pending)
        self.text.setPlainText(services.settings.recall(self.key, "draft", ""))
        self._update()

    def title(self) -> str:
        return tr("Code")

    def _project_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(152)
        box = QVBoxLayout(panel)
        box.setContentsMargins(0, 0, 6, 0)
        box.addWidget(label(tr("Project"), "heading"))
        self.open_folder = QPushButton(tr("Open folder"))
        self.open_folder.clicked.connect(self._choose_project)
        box.addWidget(self.open_folder)
        self.new_project = QPushButton(tr("New project"))
        self.new_project.clicked.connect(lambda: self._new_project())
        box.addWidget(self.new_project)
        self.recent = QComboBox()
        self.recent.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.recent.setMinimumContentsLength(12)
        self.recent.activated.connect(self._open_recent)
        box.addWidget(self.recent)
        self.project = label("", "subtitle", wrap=True)
        self.project.setTextFormat(Qt.TextFormat.PlainText)
        box.addWidget(self.project)
        self.tree = FileTree()
        self.tree.file_opened.connect(self._open_file)
        box.addWidget(self.tree, 1)
        self.undo = QPushButton(tr("Undo last edit"))
        self.undo.clicked.connect(self._undo)
        box.addWidget(self.undo)
        self.steps = QPushButton(tr("Undo history"))
        self.steps.clicked.connect(self._undo_history)
        box.addWidget(self.steps)
        return panel

    def _conversation_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(315)
        box = QVBoxLayout(panel)
        box.setContentsMargins(4, 0, 4, 0)
        model_row = QHBoxLayout()
        self.model = QComboBox()
        self.model.setAccessibleName(tr("Code model"))
        self.model.setMinimumContentsLength(12)
        self.model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.model.currentIndexChanged.connect(self._model_changed)
        model_row.addWidget(self.model, 1)
        self.context = QComboBox()
        self.context.setAccessibleName(tr("Context length"))
        self.context.addItem(tr("Auto"), 0)
        for size in CONTEXTS:
            self.context.addItem(tr("{size}K tokens", size=size // 1024), size)
        saved_context = self.services.settings.recall(self.key, "ctx", 0)
        self.context.setCurrentIndex(max(0, self.context.findData(saved_context)))
        self.context.currentIndexChanged.connect(self._refresh_readiness)
        model_row.addWidget(self.context)
        box.addLayout(model_row)

        self.model_hint = label("", "faint", wrap=True)
        box.addWidget(self.model_hint)
        warning = tr("Code can change files in this project. Approved shell commands run with "
                     "your account permissions. Choose a project folder you trust.")
        self.safety = label(warning, "warn", wrap=True)
        self.safety.setVisible(not self.services.settings.recall(self.key, "intro_seen", False))
        self.dismiss = QPushButton(tr("Got it"))
        self.dismiss.setVisible(not self.safety.isHidden())
        self.dismiss.clicked.connect(self._dismiss)
        box.addWidget(self.safety)
        box.addWidget(self.dismiss, alignment=Qt.AlignmentFlag.AlignLeft)

        self.messages = QScrollArea()
        self.messages.setWidgetResizable(True)
        self.messages.setFrameShape(QScrollArea.Shape.NoFrame)
        self.messages.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.feed = QVBoxLayout(content)
        self.feed.setContentsMargins(0, 4, 3, 4)
        self.feed.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages.setWidget(content)
        box.addWidget(self.messages, 1)
        self.examples = label(tr("Try a short script, a small web page or a focused change in a few files."),
                              "faint", wrap=True)
        box.addWidget(self.examples)
        self.state = label("", "subtitle", wrap=True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        box.addWidget(self.state)

        self.mode = Segmented([])
        self.mode.changed.connect(self._update)
        box.addWidget(self.mode)
        self.text = ComposerEdit()
        self.text.setPlaceholderText(tr("Describe a coding task or ask about this project…"))
        self.text.setAccessibleName(tr("Coding task"))
        self.text.setFixedHeight(66)
        self.text.textChanged.connect(self._update)
        box.addWidget(self.text)
        controls = QHBoxLayout()
        self.mic = MicButton(self, self.text)
        controls.addWidget(self.mic)
        self.auto_apply = QCheckBox(tr("Auto-apply"))
        self.auto_apply.setToolTip(tr("Applies text edits in this session. Deletion always asks."))
        self.auto_apply.toggled.connect(self._auto_apply)
        controls.addWidget(self.auto_apply, 1)
        self.send_task = QPushButton(tr("Send"))
        self.send_task.setProperty("role", "accent")
        self.send_task.clicked.connect(self.generate)
        controls.addWidget(self.send_task)
        self.stop = QPushButton(tr("Stop"))
        self.stop.clicked.connect(self.cancel)
        controls.addWidget(self.stop)
        box.addLayout(controls)
        return panel

    def _inspector(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(165)
        box = QVBoxLayout(panel)
        box.setContentsMargins(6, 0, 0, 0)
        self.inspector = QTabWidget()
        self.source = preview(tr("File"))
        self.diff = preview(tr("Changes"))
        self.output = preview(tr("Command output"))
        self.inspector.addTab(self.source, tr("File"))
        self.inspector.addTab(self.diff, tr("Changes"))
        self.inspector.addTab(self.output, tr("Output"))
        self._highlighters = (CodeHighlight(self.source), CodeHighlight(self.diff, diff=True))
        box.addWidget(self.inspector)
        self.discuss = QPushButton(tr("Discuss in the chat"))
        self.discuss.clicked.connect(self._discuss)
        box.addWidget(self.discuss)
        self.external = QPushButton(tr("Open in editor"))
        self.external.clicked.connect(self._external)
        box.addWidget(self.external)
        self.status_git = QPushButton(tr("Git status"))
        self.status_git.clicked.connect(self._git)
        box.addWidget(self.status_git)
        self.source.selectionChanged.connect(self._file_actions)
        return panel

    def _dismiss(self) -> None:
        self.services.settings.remember(self.key, intro_seen=True)
        self.safety.hide()
        self.dismiss.hide()

    def _choose_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("Open folder"))
        if path:
            self.open_project(Path(path))

    def _open_recent(self, index: int) -> None:
        path = self.recent.itemData(index)
        if path:
            self.open_project(Path(path))

    def open_project(self, path: Path, selected: set[str] | None = None) -> bool:
        if self.worker.isRunning() and (self.workspace is not None or self.worker.request is None
                                        or self.worker.request.workspace.root != path):
            return False
        try:
            workspace = Workspace(path)
            session = self.worker.store.load(workspace)
            self.worker.store.checkpoints(workspace)
        except (WorkspaceError, OSError) as exc:
            self._problem(exc)
            return False
        self.workspace = workspace
        self._recent = [str(workspace.root), *[old for old in self._recent if old != str(workspace.root)][:9]]
        self.recent.clear()
        self.recent.addItem(tr("Recent projects"))
        for path_str in self._recent:
            if Path(path_str).is_dir():
                self.recent.addItem(Path(path_str).name, path_str)
        self.project.setText(workspace.root.name)
        self.project.setToolTip(str(workspace.root))
        self.tree.clear()
        self._refresh_files(selected)
        self._current_file = ""
        for pane in (self.source, self.diff, self.output):
            pane.clear()
        self._clear_feed()
        for message in session.messages:
            if message["role"] in ("user", "assistant") and message.get("content"):
                content = message["content"].split("\n\nSelected project files:\n", 1)[0]
                self._message(Message(message["role"], content))
        if session.model_id:
            self._preferred_model = session.model_id
            self._models()
        saved_mode = self.services.settings.recall(self.key, "mode", session.mode)
        if self.model.currentData() and (spec := self.services.catalog.get(self.model.currentData())):
            self.mode.set_value(saved_mode if "tools" in spec.capabilities else "edit")
        self.auto_apply.blockSignals(True)
        self.auto_apply.setChecked(self.worker.permissions(workspace).auto_apply)
        self.auto_apply.blockSignals(False)
        self.state.clear()
        self._update()
        return True

    def _new_project(self, files: dict[str, str] | None = None) -> None:
        if self.worker.isRunning():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("New project"))
        form = QFormLayout(dialog)
        name = QLineEdit(tr("My project"))
        name.selectAll()
        form.addRow(tr("Project name"), name)
        template = QComboBox()
        templates = (("empty", tr("Empty project")), ("web", tr("Web page")), ("python", tr("Python script")))
        for key, title in templates:
            template.addItem(title, key)
        if files is None:
            form.addRow(tr("Template"), template)
        error = label("", "bad", wrap=True)
        error.setTextFormat(Qt.TextFormat.PlainText)
        form.addRow(error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        form.addRow(buttons)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._create_project(name.text().strip(), template.currentData(), files)
            except (WorkspaceError, OSError) as exc:
                error.setText(str(exc))
            else:
                break

    def _create_project(self, name: str, template: str = "empty",
                        files: dict[str, str] | None = None) -> None:
        if not name or any(char in name for char in "/\\"):
            raise WorkspaceError("outside", name)
        base = self.services.settings.output_path() / "projects"
        base.mkdir(parents=True, exist_ok=True)
        projects = Workspace(base)
        target = projects.resolve(name)
        contents = files
        if contents is None:
            directory = paths.package_dir() / "data" / "code_templates" / template
            contents = {filename: (directory / filename).read_text(encoding="utf-8")
                        for filename in _TEMPLATES[template]}
        for filename in contents:
            if not projects.resolve(f"{name}/{filename}").is_relative_to(target):
                raise WorkspaceError("outside", filename)
        target.mkdir(exist_ok=False)
        project = Workspace(target)
        for filename, source in contents.items():
            project.apply(project.propose_write(filename, source))
        self.open_project(target, set(contents))

    def _models(self, *_args: object) -> None:
        current = self._preferred_model
        specs = [model for model in self.services.catalog.all("chat") if self.services.installed(model)]
        specs.sort(key=lambda model: ("code" not in model.tags, "tools" not in model.capabilities,
                                      model.download_gb))
        self.model.blockSignals(True)
        self.model.clear()
        for spec in specs:
            self.model.addItem(spec.name, spec.id)
        if self.model.findData(current) >= 0:
            self.model.setCurrentIndex(self.model.findData(current))
        if not specs:
            self.model.addItem(tr("Install a chat model"), "")
        self.model.blockSignals(False)
        self._model_changed()

    def _model_changed(self, *_args: object) -> None:
        spec = self.services.catalog.get(self.model.currentData() or "")
        if spec is not None:
            self._preferred_model = spec.id
        modes = [("agent", tr("Agent")), ("edit", tr("Edits")), ("question", tr("Question"))]
        former = self.mode.value() or "edit"
        self.mode.set_options(modes)
        tools = spec is not None and "tools" in spec.capabilities
        self.mode.set_option_enabled("agent", tools)
        self.mode.set_option_enabled("question", tools)
        self.mode.set_value(former if tools else "edit")
        self._refresh_readiness()

    def _choose_context(self, spec: ModelSpec) -> int:
        ceiling = spec.context or CONTEXTS[-1]
        force = self.context.currentData()
        if force:
            return min(force, ceiling)
        options = sorted({min(size, ceiling) for size in CONTEXTS})
        ranks = (advisor.GREAT, advisor.GOOD, advisor.SLOW, advisor.VERY_SLOW, advisor.NO)
        best, quality = options[0], len(ranks)
        for size in options:
            fit = self.services.fit(spec, ctx=size)
            rank = ranks.index(fit.verdict) if fit else len(ranks)
            if rank <= quality:
                best, quality = size, rank
        return best

    def _refresh_readiness(self, *_args: object) -> None:
        spec = self.services.catalog.get(self.model.currentData() or "")
        self._context = self._choose_context(spec) if spec else 0
        chosen = tr("The coding model uses {size}K tokens of context.", size=self._context // 1024)
        self.context.setToolTip(chosen if spec else "")
        self.context.setItemText(0, tr("Auto · {size}K", size=self._context // 1024)
                                 if spec and not self.context.currentData() else tr("Auto"))
        selected_runtime = self.services.chat_runtime()
        has_runtime = selected_runtime is not None and self.services.installed(selected_runtime)
        fit = self.services.fit(spec, ctx=self._context) if spec else None
        self._model_ready = bool(has_runtime and fit and fit.ok)
        hint = ""
        if spec is None or not has_runtime:
            hint = tr("Install a local chat model and its engine on the Models page.")
        elif fit and not fit.ok:
            hint = messages.engine_error("does_not_fit")
        elif "tools" not in spec.capabilities:
            hint = tr("This model supports the Edits mode. Agent and Question need tool support.")
        elif 0 < self.services.store.size_bytes(spec) < 3 * 1024**3:
            hint = tr("Small models may struggle with multi-step tasks. Try Edits for targeted changes.")
        self.model_hint.setText(hint)
        self.model_hint.setVisible(bool(hint))
        self._update()

    def _update(self, *_args: object) -> None:
        busy = self.worker.isRunning()
        ready = self.workspace is not None
        has_task = bool(self.text.toPlainText().strip())
        files_ready = not self._files_loading or self.mode.value() == "agent"
        self.send_task.setEnabled(not busy and ready and self._model_ready and has_task and files_ready)
        self.examples.setVisible(not self.feed.count() and not busy)
        self.stop.setEnabled(busy)
        for control in (self.open_folder, self.new_project, self.recent, self.model, self.context, self.mode):
            control.setEnabled(not busy)
        for control in (self.tree, self.auto_apply, self.undo, self.steps):
            control.setEnabled(ready and not busy)
        self.text.setReadOnly(busy)
        self.mic.setEnabled(not busy and self.mic.state != "listening")
        self.status_git.setEnabled(ready)
        self._file_actions()
        if not busy and not self.state.text() and not ready:
            self.state.setText(tr("Open a project to edit files, ask about code or run a local check."))

    def _auto_apply(self, active: bool) -> None:
        if self.workspace is not None and not self.worker.isRunning():
            self.worker.permissions(self.workspace).auto_apply = active

    def generate(self) -> None:
        if not self.send_task.isEnabled() or self.workspace is None or self.mic.state != "idle":
            return
        spec = self.services.catalog.get(self.model.currentData() or "")
        launch = self.services.chat_launch(spec, self._context) if spec else None
        if launch is None or spec is None:
            self._failed("no_chat_model", "")
            return
        mode = self.mode.value()
        image = self._image_model() if mode == "agent" else None
        task = self.text.toPlainText().strip()
        request = Request(self.workspace, launch, task, mode, self.tree.checked() if mode != "agent" else (),
                          "tools" in spec.capabilities, image)
        if self.worker.submit(request):
            self.state.setText(tr("Working on the project…"))
            self.text.clear()
            self._update()

    def _image_model(self) -> ModelSpec | None:
        for spec in self.services.catalog.all("image"):
            if spec.source != "online" and not spec.requires_reference and self.services.installed(spec):
                fit = self.services.fit(spec)
                if fit and fit.ok:
                    return spec
        return None

    def cancel(self) -> None:
        if self.worker.isRunning():
            self.worker.cancel()
            self._remove_approval()

    def _clear_feed(self) -> None:
        while self.feed.count():
            item = self.feed.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._live, self._approval, self._tool = None, None, None

    def _message(self, message: Message) -> None:
        view = MessageView(message, 0, full_width=True)
        view.setProperty("code_text", message.content)
        for button in view.buttons[1:]:
            button.hide()
        view.action.connect(self._copy_message)
        self.feed.addWidget(view)
        self.examples.hide()
        self._follow()

    def _copy_message(self, _action: str, _index: int) -> None:
        from PySide6.QtGui import QGuiApplication

        view = self.sender()
        if isinstance(view, MessageView):
            QGuiApplication.clipboard().setText(view.property("code_text"))

    def _follow(self) -> None:
        QTimer.singleShot(0, self, self._scroll_bottom)

    def _scroll_bottom(self) -> None:
        bar = self.messages.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _delta(self, text: str, reasoning: str) -> None:
        if self._live is None:
            self._stream = Message("assistant")
            self._live = MessageView(self._stream, 0, live=True)
            self.feed.addWidget(self._live)
        self._stream.content += text
        self._stream.reasoning += reasoning
        self._live.update_from(self._stream, live=True)
        self._follow()

    def _end_live(self) -> None:
        if self._live is not None:
            self.feed.removeWidget(self._live)
            self._live.hide()
            self._live.deleteLater()
            self._live = None

    def _event(self, event: Event) -> None:
        if event.kind in ("user", "assistant"):
            self._end_live()
            self._message(Message(event.kind, event.text))
        elif event.kind == "tool":
            labels = {"list_files": tr("List project files"), "read_file": tr("Read file"),
                      "search": tr("Search project"), "write_file": tr("Proposed change"),
                      "edit_file": tr("Proposed change"), "delete_file": tr("Delete file"),
                      "run_command": tr("Run command"), "generate_image": tr("Create image asset"),
                      "finish": tr("Task finished.")}
            self._tool = Disclosure(labels.get(event.label, event.label))
            details = preview(event.label)
            details.setMaximumHeight(85)
            details.setPlainText(event.text)
            self._tool.body.addWidget(details)
            self.feed.addWidget(self._tool)
        elif event.kind == "tool_result" and self._tool is not None:
            if event.label == "run_command":
                self.output.setPlainText(event.text)
                self.inspector.setCurrentWidget(self.output)
            result = preview(event.label)
            result.setPlainText(event.text)
            result.setMaximumHeight(130)
            self._tool.body.addWidget(result)
        elif event.kind == "applied":
            self._status_line(tr("Applied {path}", path=event.label))
            self._refresh_files()
            if event.label == self._current_file:
                self._open_file(event.label)
        elif event.kind == "compacted":
            self._status_line(tr("Earlier messages were summarized."))
        elif event.kind == "edit_error":
            self._status_line(f"{event.label}\n{event.text}")
            retry = QPushButton(tr("Ask the model to fix the edit"))
            retry.clicked.connect(lambda _=False, error=event: self._repair(error))
            self.feed.addWidget(retry, alignment=Qt.AlignmentFlag.AlignLeft)
        self._follow()

    def _status_line(self, message: str) -> None:
        notice = label(message, "faint", wrap=True)
        notice.setTextFormat(Qt.TextFormat.PlainText)
        self.feed.addWidget(notice)

    def _repair(self, event: Event) -> None:
        if self.worker.isRunning() or self.workspace is None:
            return
        self.tree.mark(event.label)
        self.text.setPlainText(tr("Fix the proposed change to {path}. The earlier edit failed: {reason}",
                                 path=event.label, reason=event.text))
        self.generate()

    def _approve(self, identifier: int, approval: Approval) -> None:
        self._remove_approval()
        self._approval = ApprovalCard(identifier, approval)
        self._approval.decided.connect(self._resolve)
        self.feed.addWidget(self._approval)
        if approval.kind in {"write", "delete", "image"}:
            self.diff.setPlainText(approval.detail)
            self.inspector.setCurrentWidget(self.diff)
        self._follow()

    def _remove_approval(self) -> None:
        if self._approval is not None:
            self.feed.removeWidget(self._approval)
            self._approval.hide()
            self._approval.deleteLater()
            self._approval = None

    def _resolve(self, identifier: int, action: str, note: str) -> None:
        self._remove_approval()
        self.worker.resolve(identifier, action, note)

    def _failed(self, code: str, detail: str) -> None:
        if code == "context_overflow":
            text = tr("The task and selected files exceed the context. "
                      "Select fewer files or a longer context.")
        else:
            text = detail or messages.llm_error(code)
        self.state.setText(text)

    def _settled(self, status: str) -> None:
        self._end_live()
        self._remove_approval()
        if status != "failed":
            statuses = {"done": tr("Task finished."), "cancelled": tr("Cancelled."),
                        "loop": tr("The model repeated the same action and stopped."),
                        "step_limit": tr("The model reached 30 steps. Send a message to continue.")}
            self.state.setText(statuses[status])
        if self.workspace is not None:
            self.auto_apply.blockSignals(True)
            self.auto_apply.setChecked(self.worker.permissions(self.workspace).auto_apply)
            self.auto_apply.blockSignals(False)
        self._update()

    def _refresh_files(self, selected: set[str] | None = None) -> None:
        workspace = self.workspace
        if workspace is None:
            return
        self._files_loading = True
        self._files_token += 1
        token = self._files_token
        self._update()

        def snapshot() -> tuple[int, list[str] | OSError, set[str] | None]:
            try:
                return token, workspace.tree(), selected
            except OSError as exc:
                return token, exc, selected

        run_async(snapshot, self._files_ready)

    def _files_ready(self, result: tuple[int, list[str] | OSError, set[str] | None]) -> None:
        token, files, selected = result
        if token != self._files_token:
            return
        self._files_loading = False
        if isinstance(files, OSError):
            self._problem(files)
        else:
            checked = set(self.tree.checked()) if selected is None else selected
            self.tree.fill(files, checked)
        self._update()

    def _open_file(self, relative: str) -> None:
        if self.workspace is None:
            return
        self._current_file = relative
        self.inspector.setCurrentWidget(self.source)
        try:
            source = self.workspace.propose_delete(relative).before or ""
            self.source.setPlainText(source[:100_000])
        except (WorkspaceError, OSError) as exc:
            self.source.clear()
            self._problem(exc)
        self._file_actions()

    def _file_actions(self) -> None:
        self.discuss.setEnabled(self.source.textCursor().hasSelection())
        self.external.setEnabled(bool(self._current_file))
        self.external.setText(tr("Open in browser") if self._current_file.endswith((".html", ".htm"))
                              else tr("Open in editor"))

    def _external(self) -> None:
        if self.workspace is not None and self._current_file:
            try:
                file = self.workspace.resolve(self._current_file)
                if file.is_file():
                    if file.suffix.lower() in {".html", ".htm"}:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(file)))
                    elif not self._open_text_editor(file):
                        self.state.setText(tr("No text editor could be found."))
            except (WorkspaceError, OSError) as exc:
                self._problem(exc)

    @staticmethod
    def _open_text_editor(file: Path) -> bool:
        if sys.platform == "win32":
            editor = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "notepad.exe"
            return QProcess.startDetached(str(editor), [str(file)])[0]
        if sys.platform == "darwin":
            return QProcess.startDetached("/usr/bin/open", ["-e", str(file)])[0]
        system_path = os.pathsep.join(entry for entry in os.get_exec_path() if Path(entry).is_absolute())
        for editor in ("code", "gedit", "kate", "mousepad"):
            if (executable := shutil.which(editor, path=system_path)) and QProcess.startDetached(
                    executable, [str(file)])[0]:
                return True
        return False

    def _discuss(self) -> None:
        cursor = self.source.textCursor()
        if cursor.hasSelection():
            content = cursor.selectedText().replace("\u2029", "\n")
            self.send(handoff.text(f"{self._current_file}\n\n```\n{content}\n```", self.key), "chat", "text")

    def _git(self) -> None:
        if self.workspace is not None:
            workspace = self.workspace
            run_async(lambda: git_status(workspace.root), self._show_git, self._problem)

    def _show_git(self, status: str) -> None:
        self.output.setPlainText(status or tr("No changes reported by Git."))
        self.inspector.setCurrentWidget(self.output)

    def _undo(self) -> None:
        if self.workspace is None or self.worker.isRunning():
            return
        try:
            if self.worker.store.checkpoints(self.workspace).undo_last():
                self._after_undo()
        except (WorkspaceError, OSError, ValueError) as exc:
            self._problem(exc)

    def _undo_history(self) -> None:
        if self.workspace is None or self.worker.isRunning():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Undo history"))
        box = QVBoxLayout(dialog)
        checkpoints = self.worker.store.checkpoints(self.workspace)
        steps = QComboBox()
        try:
            for number, path, when in checkpoints.steps():
                stamp = time.strftime("%d.%m %H:%M", time.localtime(when))
                steps.addItem(f"{number} · {path} · {stamp}", number - 1)
            if not steps.count():
                self.state.setText(tr("No applied edits yet."))
                return
            box.addWidget(label(tr("Undo this edit and every later edit."), "subtitle"))
            box.addWidget(steps)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                       | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            box.addWidget(buttons)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                checkpoints.undo_to(steps.currentData())
                self._after_undo()
        except (WorkspaceError, OSError, ValueError) as exc:
            self._problem(exc)

    def _after_undo(self) -> None:
        self._refresh_files()
        if self._current_file:
            self._open_file(self._current_file)
        self.state.setText(tr("Edits reverted."))

    def _problem(self, error: object) -> None:
        self.state.setText(str(error))

    def routes(self, asset: Asset) -> list[Route]:
        if asset.kind == "text" and asset.source == "chat" and code_files(asset.text):
            return [Route(self.key, "code_blocks", tr("Open in Code"), "code")]
        return []

    def receive(self, asset: Asset, role: str) -> None:
        if role != "code_blocks":
            return
        files = code_files(asset.text)
        if files:
            self._new_project(files)

    def save_state(self) -> None:
        self.mic.discard()
        self.services.settings.remember(self.key, recent=self._recent,
                                        project=str(self.workspace.root) if self.workspace else "",
                                        selected=list(self.tree.checked()), draft=self.text.toPlainText(),
                                        model=self._preferred_model, ctx=self.context.currentData(),
                                        mode=self.mode.value(),
                                        split=self.split.sizes())
