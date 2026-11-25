"""Plan, edit and assemble a short video from the Chat page."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tvorka.core import advisor, storyboard
from tvorka.core.catalog import ModelSpec
from tvorka.core.jobs import Job
from tvorka.core.llm.prompts import prompt_style
from tvorka.gui.widgets.basic import label
from tvorka.gui.widgets.mic import MicButton
from tvorka.i18n import language, messages, tr

if TYPE_CHECKING:
    from tvorka.gui.pages.chat import ChatPage


class StoryboardDialog(QDialog):
    def __init__(self, page: ChatPage, idea: str, parent_id: str) -> None:
        super().__init__(page)
        self.services, self.toasts = page.services, page.toasts
        self._parent_id = parent_id
        self._planned_for = ("", "")
        self._request = self._job = 0
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(tr("Video from an idea"))
        self.resize(850, 690)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.addWidget(label(tr("Video from an idea"), "title"))
        self.idea = QPlainTextEdit(idea)
        self.idea.setPlaceholderText(tr("Describe a short video or dictate your idea."))
        self.idea.setAccessibleName(tr("Video idea"))
        self.idea.setFixedHeight(68)
        self.idea.textChanged.connect(self._update_actions)
        layout.addWidget(self.idea)

        inputs = QHBoxLayout()
        self.mic = MicButton(self, self.idea)
        inputs.addWidget(self.mic)
        self.count = QSpinBox()
        self.count.setRange(1, storyboard.MAX_SCENES)
        self.count.setValue(3)
        count_label = label(tr("Number of scenes"))
        count_label.setBuddy(self.count)
        inputs.addWidget(count_label)
        inputs.addWidget(self.count)
        self.language = QComboBox()
        self.language.addItem(tr("Russian narration"), "ru")
        self.language.addItem(tr("English narration"), "en")
        self.language.setCurrentIndex(self.language.findData(language()))
        self.language.currentIndexChanged.connect(self._models_changed)
        inputs.addWidget(self.language)
        inputs.addStretch()
        self.plan = QPushButton(tr("Draft storyboard"))
        self.plan.clicked.connect(self._plan)
        inputs.addWidget(self.plan)
        layout.addLayout(inputs)

        self.table = QTableWidget(0, 3)
        self.table.setAccessibleName(tr("Storyboard"))
        self.table.setHorizontalHeaderLabels([tr("Image prompt"), tr("Motion"), tr("Narration")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setMinimumSectionSize(54)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setWordWrap(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._update_actions)
        self.table.currentCellChanged.connect(self._update_actions)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.up = QPushButton(tr("Move scene up"))
        self.down = QPushButton(tr("Move scene down"))
        self.remove = QPushButton(tr("Remove scene"))
        self.up.clicked.connect(self._move_up)
        self.down.clicked.connect(self._move_down)
        self.remove.clicked.connect(self._remove)
        for button in (self.up, self.down, self.remove):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)

        self.models = QWidget()
        form = QFormLayout(self.models)
        form.setContentsMargins(0, 2, 0, 0)
        self.image, self.video, self.speech = QComboBox(), QComboBox(), QComboBox()
        form.addRow(tr("Image model"), self.image)
        form.addRow(tr("Image-to-video model"), self.video)
        form.addRow(tr("Voice model"), self.speech)
        layout.addWidget(self.models)
        self.requirements = label("", "subtitle", wrap=True)
        layout.addWidget(self.requirements)

        self.status = label("", "subtitle", wrap=True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)
        footer = QHBoxLayout()
        self.close_button = QPushButton(tr("Close"))
        self.close_button.clicked.connect(self.reject)
        self.stop = QPushButton(tr("Cancel"))
        self.stop.clicked.connect(self._stop)
        self.build = QPushButton(tr("Assemble video"))
        self.build.setProperty("role", "accent")
        self.build.clicked.connect(self._build)
        self.gallery = QPushButton(tr("Open Gallery"))
        self.gallery.clicked.connect(self._open_gallery)
        self.gallery.hide()
        footer.addWidget(self.close_button)
        footer.addStretch()
        for button in (self.gallery, self.stop, self.build):
            footer.addWidget(button)
        layout.addLayout(footer)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)

        self.services.models_changed.connect(self._models_changed)
        self.services.hardware_ready.connect(self._models_changed)
        worker = self.services.worker
        worker.job_progress.connect(self._on_progress)
        worker.job_finished.connect(self._on_finished)
        worker.job_failed.connect(self._on_failed)
        worker.job_cancelled.connect(self._on_cancelled)
        self._models_changed()

    def _models_changed(self, *_args: object) -> None:
        for kind, combo in (("image", self.image), ("video", self.video), ("speech", self.speech)):
            selected = combo.currentData() or self.services.settings.recall(kind, "model", "")
            combo.clear()
            for spec in self.services.catalog.all(kind):
                if self._usable_model(spec):
                    combo.addItem(spec.name, spec)
                    if spec.id == getattr(selected, "id", selected):
                        combo.setCurrentIndex(combo.count() - 1)
            if not combo.count():
                combo.addItem(tr("No compatible model installed"))
        self._update_actions()

    def _usable_model(self, spec: ModelSpec) -> bool:
        if spec.source == "online" or (spec.kind == "image" and spec.requires_reference):
            return False
        if spec.kind == "video" and "i2v" not in spec.reference:
            return False
        if spec.kind == "speech" and spec.languages and self.language.currentData() not in spec.languages:
            return False
        if not self.services.installed(spec):
            return False
        reference = "i2v" if spec.kind == "video" else ""
        scale = advisor.work_scale(spec, *spec.native, advisor.video_frames(spec)[0]) if reference else 1.0
        fit = self.services.fit(spec, scale=scale, reference=reference)
        return fit is None or fit.ok

    def _update_actions(self, *_args: object) -> None:
        idea = self.idea.toPlainText().strip()
        busy = bool(self._request or self._job)
        ready = all(combo.currentData() for combo in (self.image, self.video, self.speech))
        row, count = self.table.currentRow(), self.table.rowCount()
        for widget in (self.idea, self.count, self.language, self.table, self.models):
            widget.setEnabled(not busy)
        self.mic.setEnabled(not busy and self.mic.state != "listening")
        self.plan.setEnabled(not busy and bool(idea))
        self.up.setEnabled(not busy and row > 0)
        self.down.setEnabled(not busy and 0 <= row < count - 1)
        self.remove.setEnabled(not busy and row >= 0)
        self.stop.setEnabled(busy)
        self.requirements.setText("" if ready else tr(
            "Install a compatible local image, image-to-video or voice model on the Models page."))
        self.requirements.setVisible(not ready)
        self.build.setEnabled(not busy and ready and self._planned_for == (idea, self.language.currentData())
                              and bool(self._scenes()))

    def _scenes(self) -> list[storyboard.Scene]:
        scenes = []
        for row in range(self.table.rowCount()):
            items = [self.table.item(row, col) for col in range(self.table.columnCount())]
            texts = [item.text().strip() if item is not None else "" for item in items]
            if not all(texts):
                return []
            scenes.append(storyboard.Scene(*texts))
        return scenes

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(1)

    def _move(self, offset: int) -> None:
        row, col = self.table.currentRow(), self.table.currentColumn()
        other = row + offset
        if row < 0 or not 0 <= other < self.table.rowCount():
            return
        for column in range(self.table.columnCount()):
            a = self.table.takeItem(row, column)
            b = self.table.takeItem(other, column)
            self.table.setItem(row, column, b)
            self.table.setItem(other, column, a)
        self.table.setCurrentCell(other, col)

    def _remove(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._update_actions()

    def _plan(self) -> None:
        if self.mic.state != "idle":
            self.status.setText(tr("Finish dictation first."))
            return
        idea, lang, count = self.idea.toPlainText().strip(), self.language.currentData(), self.count.value()
        style = prompt_style(self.image.currentData())
        self.status.setText(tr("Drafting the storyboard…"))
        self._request = self.services.assistant.ask(storyboard.plan(idea, count, lang, style),
                                                    lambda answer: self._planned(answer, idea, lang, count),
                                                    self._plan_failed)
        self._update_actions()

    def _planned(self, answer: str, idea: str, lang: str, count: int) -> None:
        self._request = 0
        try:
            scenes = storyboard.parse(answer, count)
        except ValueError:
            self.status.setText(tr("The storyboard was incomplete. Try drafting it again."))
        else:
            self._planned_for = (idea, lang)
            self.table.setRowCount(len(scenes))
            for row, scene in enumerate(scenes):
                for col, value in enumerate(asdict(scene).values()):
                    self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.setCurrentCell(0, 0)
            self.status.setText(tr("Review the scenes, then assemble the video."))
        self._update_actions()

    def _plan_failed(self, code: str) -> None:
        self._request = 0
        self.status.setText(tr("Install a local chat model on the Models page to draft the storyboard.")
                            if code == "no_chat_model" else messages.llm_error(code))
        self._update_actions()

    def _build(self) -> None:
        if self.mic.state != "idle":
            self.status.setText(tr("Finish dictation first."))
            return
        image, video, speech = (combo.currentData() for combo in (self.image, self.video, self.speech))
        params = {"storyboard": [asdict(scene) for scene in self._scenes()],
                  "image_model": image.id, "speech_model": speech.id,
                  "narration_language": self._planned_for[1], "format": "mp4"}
        if self._parent_id:
            params["parent"] = self._parent_id
        job = Job("video", video.id, self._planned_for[0], params)
        self._job = job.id
        self.progress.setValue(0)
        self.progress.show()
        self.gallery.hide()
        self.status.setText(tr("Waiting in the queue…"))
        self.services.worker.submit(job)
        self._update_actions()

    def _on_progress(self, job_id: int, fraction: float, stage: str) -> None:
        if job_id == self._job:
            self.progress.setValue(max(self.progress.value(), round(fraction * 100)))
            self.status.setText(messages.stage(stage) or tr("Being created…"))

    def _on_finished(self, job_id: int, _results: list[dict]) -> None:
        if job_id == self._job:
            self._finish(tr("The video is ready in the Gallery."))
            self.gallery.show()

    def _on_failed(self, job_id: int, code: str, _detail: str) -> None:
        if job_id == self._job:
            self._finish(messages.engine_error(code))

    def _on_cancelled(self, job_id: int) -> None:
        if job_id == self._job:
            self._finish(tr("Cancelled."))

    def _finish(self, status: str) -> None:
        self._job = 0
        self.progress.hide()
        self.status.setText(status)
        self._update_actions()

    def _stop(self) -> None:
        if self._request:
            self.services.assistant.cancel(self._request)
            self._request = 0
            self._finish(tr("Cancelled."))
        if self._job:
            self.services.worker.cancel(self._job)

    def _open_gallery(self) -> None:
        window = self.parentWidget().window()
        page = window.page("gallery")
        if page is not None:
            self.mic.discard()
            self.accept()
            window.open_page(window.pages.index(page))

    def reject(self) -> None:
        self._stop()
        self.mic.discard()
        super().reject()

    def detach(self) -> None:
        """Let the shared queue finish the video if the main window is rebuilt."""
        self._job = 0
        self.reject()
