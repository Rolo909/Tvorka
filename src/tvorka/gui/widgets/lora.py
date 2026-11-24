"""Ordered list of local LoRA files and their generation weights."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from tvorka.gui.widgets.basic import label, tool_button
from tvorka.i18n import tr


class LoraPicker(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._rows: dict[str, tuple[QWidget, QDoubleSpinBox]] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.rows = QVBoxLayout()
        layout.addLayout(self.rows)
        add = QPushButton(tr("Add LoRA"))
        add.setProperty("role", "ghost")
        add.clicked.connect(self._choose)
        layout.addWidget(add, alignment=Qt.AlignmentFlag.AlignLeft)

    def _choose(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, tr("Add LoRA"), "", "LoRA (*.safetensors)")
        for file in files:
            self.add(file)

    def add(self, file: str, weight: float = 1.0) -> None:
        path = Path(file)
        if path.suffix.lower() != ".safetensors" or file in self._rows:
            return
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        name = label(path.name, "", wrap=True)
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setToolTip(file)
        layout.addWidget(name, 1)
        value = QDoubleSpinBox()
        value.setRange(-2.0, 2.0)
        value.setSingleStep(0.05)
        value.setValue(weight)
        value.setAccessibleName(tr("LoRA weight"))
        value.setToolTip(tr("LoRA weight"))
        layout.addWidget(value)
        remove = tool_button("close", tr("Remove LoRA"))
        remove.clicked.connect(lambda: self._remove(file))
        layout.addWidget(remove)
        self.rows.addWidget(row)
        self._rows[file] = (row, value)

    def _remove(self, file: str) -> None:
        row, _ = self._rows.pop(file)
        self.rows.removeWidget(row)
        row.hide()
        row.deleteLater()

    def values(self) -> list[dict[str, Any]]:
        return [{"path": file, "weight": value.value()} for file, (_, value) in self._rows.items()]

    def set_values(self, values: list[dict[str, Any]]) -> None:
        for file in list(self._rows):
            self._remove(file)
        for item in values:
            self.add(item["path"], item.get("weight", 1.0))
