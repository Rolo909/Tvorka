"""One player for the audio results of a chat page."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import QHBoxLayout, QSlider, QWidget

from tvorka.gui import icons
from tvorka.gui.widgets.basic import label, tool_button
from tvorka.i18n import tr

if TYPE_CHECKING:
    from PySide6.QtMultimedia import QMediaPlayer


class ChatAudio(QWidget):
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._player: QMediaPlayer | None = None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.play_button = tool_button("play", tr("Play"))
        self.play_button.clicked.connect(self._toggle)
        row.addWidget(self.play_button)
        row.addWidget(label(tr("Answer audio"), "muted"))
        self.position = QSlider(Qt.Orientation.Horizontal)
        self.position.setAccessibleName(tr("Playback position"))
        self.position.setRange(0, 0)
        self.position.sliderMoved.connect(self._seek)
        row.addWidget(self.position, 1)
        close = tool_button("close", tr("Close"))
        close.clicked.connect(self.clear)
        row.addWidget(close)
        self.hide()

    def play(self, path: str) -> None:
        if not Path(path).is_file():
            self.failed.emit(tr("The audio file is missing."))
            return
        if self._player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(QAudioOutput(self))
            self._player.durationChanged.connect(lambda duration: self.position.setMaximum(duration))
            self._player.positionChanged.connect(self.position.setValue)
            self._player.playbackStateChanged.connect(self._sync_button)
            self._player.errorOccurred.connect(lambda _code, detail: self.failed.emit(detail))
        source = QUrl.fromLocalFile(path)
        if self._player.source() != source:
            self._player.setSource(source)
        self.show()
        self._player.play()

    def clear(self) -> None:
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
        self.hide()

    def _toggle(self) -> None:
        if self._player is not None:
            if self._player.isPlaying():
                self._player.pause()
            else:
                self._player.play()

    def _seek(self, position: int) -> None:
        if self._player is not None:
            self._player.setPosition(position)

    def _sync_button(self) -> None:
        playing = self._player is not None and self._player.isPlaying()
        self.play_button.setIcon(icons.icon("pause" if playing else "play"))
        action = tr("Pause") if playing else tr("Play")
        self.play_button.setToolTip(action)
        self.play_button.setAccessibleName(action)
