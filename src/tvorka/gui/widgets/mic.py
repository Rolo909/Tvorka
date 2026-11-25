"""Voice input: press to record, press again — the words appear in the text field (nothing is sent)."""

from __future__ import annotations

import logging
import os
import tempfile
import time
import wave
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QToolButton, QWidget

from tvorka.gui import icons
from tvorka.i18n import messages, tr

log = logging.getLogger(__name__)
MAX_SECONDS = 300  # a longer dictation is cut here; recognition of the recording follows


def mic_bar(page: Any, target: QPlainTextEdit) -> QWidget:
    """A dictation button aligned to the right, to go under a text field."""
    bar = QWidget()
    row = QHBoxLayout(bar)
    row.setContentsMargins(0, 0, 0, 0)
    row.addStretch(1)
    page.mic = MicButton(page, target)
    row.addWidget(page.mic)
    return bar


class QtRecorder(QObject):
    """Records the default microphone to a WAV file with Qt Multimedia."""

    stopped = Signal(str)  # path of the finished recording
    error = Signal(str)
    level = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source: Any = None
        self._input: Any = None
        self._writer: wave.Wave_write | None = None
        self._file = ""
        self._pending = b""

    @staticmethod
    def available() -> bool:
        from PySide6.QtMultimedia import QMediaDevices

        return bool(QMediaDevices.audioInputs())

    def record(self, file: Path) -> None:
        from PySide6.QtMultimedia import QAudio, QAudioSource, QMediaDevices

        self._file = str(file)
        device = QMediaDevices.defaultAudioInput()
        fmt = device.preferredFormat()
        if device.isNull() or not fmt.isValid():
            self.error.emit(tr("No usable audio format for this microphone."))
            return
        try:
            self._writer = wave.open(self._file, "wb")  # noqa: SIM115 - closed when recording ends
            self._writer.setnchannels(fmt.channelCount())
            self._writer.setsampwidth(2)
            self._writer.setframerate(fmt.sampleRate())
            self._pending = b""
            self._source = QAudioSource(device, fmt, self)
            self._input = self._source.start()
        except OSError as exc:
            self._finish(str(exc))
            return
        # PySide6 exposes distinct enum wrappers for QAudio and QtAudio on some versions.
        if self._input is None or self._source.error().value != QAudio.Error.NoError.value:
            self._finish(tr("The microphone could not start recording."))
            return
        self._source.stateChanged.connect(self._state)
        self._input.readyRead.connect(self._consume)

    def stop(self) -> None:
        if self._source is not None:
            self._consume()
            if self._source is not None:  # reading may have failed
                self._finish()

    def _state(self, state: Any) -> None:
        from PySide6.QtMultimedia import QAudio

        if state.value == QAudio.State.StoppedState.value and self._source is not None:
            self._finish(tr("The microphone stopped recording."))

    def _consume(self) -> None:
        if self._source is None or self._writer is None:
            return
        fmt = self._source.format()
        data = self._pending + bytes(self._input.readAll())
        end = len(data) - len(data) % fmt.bytesPerFrame()
        self._pending = data[end:]
        if not end:
            return
        samples, level = _pcm16(data[:end], fmt.sampleFormat())
        try:
            self._writer.writeframesraw(samples)
        except OSError as exc:
            self._finish(str(exc))
            return
        self.level.emit(level)

    def _finish(self, error: str = "") -> None:
        source, self._source = self._source, None
        if source is not None:
            source.stop()
            source.deleteLater()
        self._input = None
        writer, self._writer = self._writer, None
        if writer is not None:
            try:
                writer.close()
            except OSError as exc:
                error = error or str(exc)
        if error:
            self.error.emit(error)
        else:
            self.stopped.emit(self._file)


def _pcm16(data: bytes, sample_format: Any) -> tuple[bytes, int]:
    """Convert native input samples for the WAV writer and measure their peak."""
    import numpy as np
    from PySide6.QtMultimedia import QAudioFormat

    formats = QAudioFormat.SampleFormat
    if sample_format == formats.Int16:
        samples = np.frombuffer(data, dtype=np.int16)
    elif sample_format == formats.Int32:
        samples = np.frombuffer(data, dtype=np.int32) >> 16
    elif sample_format == formats.UInt8:
        samples = (np.frombuffer(data, dtype=np.uint8).astype(np.int16) - 128) << 8
    else:  # Qt's remaining PCM format is Float
        samples = np.clip(np.frombuffer(data, dtype=np.float32), -1, 1) * 32767
    samples = samples.astype("<i2", copy=False)
    peak = int(np.abs(samples.astype(np.int32)).max(initial=0))
    return samples.tobytes(), round(100 * peak / 32768)


class MicButton(QToolButton):
    """Dictation into ``target``. ``page`` gives the services and the toasts."""

    def __init__(self, page: Any, target: QPlainTextEdit) -> None:
        super().__init__()
        self.page, self.target = page, target
        self.setProperty("role", "ghost")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.recorder: Any = None  # created on first use; tests put a stand-in here
        self._wired: Any = None  # the recorder whose signals are connected
        self._started = 0.0
        self._request = 0
        self._future: Future[str] | None = None
        self._file: Path | None = None
        self._level = 0
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)
        self.clicked.connect(self._clicked)
        stt = page.services.stt
        stt.transcribed.connect(self._on_text)
        stt.failed.connect(self._on_failed)
        self._show("idle")

    @property
    def state(self) -> str:
        return str(self.property("state") or "idle")

    def _show(self, state: str) -> None:
        self.setProperty("state", state)
        self.setProperty("recording", state == "recording")
        self.style().unpolish(self)
        self.style().polish(self)
        glyph, color, tip = {
            "idle": ("mic", "text", tr("Dictate: press, speak, press again — the text appears here")),
            "recording": ("stop", "bad", tr("Stop and turn the speech into text")),
            "listening": ("refresh", "muted", tr("Recognizing speech…")),
        }[state]
        self.setIcon(icons.icon(glyph, color))
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        if state != "recording":
            self._level = 0
        if state == "idle":
            self.setText("")
        self.setEnabled(state != "listening")

    def _toast(self, text: str, level: str = "warn") -> None:
        toasts = getattr(self.page, "toasts", None)
        if toasts is not None:
            toasts.show(text, level)

    def _clicked(self) -> None:
        if self.state == "recording":
            self.stop()
            return
        if self.page.services.stt_model() is None:
            self._toast(tr("Voice input needs a speech recognition model. Download one on the Models page "
                           "(Speech recognition): Whisper small suits most computers."))
            return
        if self.recorder is None:
            if not QtRecorder.available():
                self._toast(tr("No microphone found. Connect one and allow Windows to use it "
                               "(Settings → Privacy → Microphone)."))
                return
            self.recorder = QtRecorder(self)
        if self._wired is not self.recorder:
            self.recorder.stopped.connect(self._recorded)
            self.recorder.error.connect(self._record_error)
            if hasattr(self.recorder, "level"):
                self.recorder.level.connect(self._on_level)
            self._wired = self.recorder
        handle, name = tempfile.mkstemp(prefix="tvorka-voice-", suffix=".wav")
        os.close(handle)
        self._file = Path(name)
        self._started = time.monotonic()
        self._show("recording")
        self._tick()
        self._timer.start()
        self.recorder.record(self._file)

    def stop(self) -> None:
        if self.state == "recording" and self.recorder is not None:
            self._timer.stop()
            self._show("listening")
            self.setText(tr("Recognizing…"))
            self.recorder.stop()

    def discard(self) -> None:
        """Release a transient input's recording when its dialog closes."""
        recording = self.state == "recording"
        self._timer.stop()
        self._show("idle")
        if recording:
            self.recorder.stop()
        if self._future is not None and self._file is not None:
            path, self._file = self._file, None
            self._future.add_done_callback(lambda _done: path.unlink(missing_ok=True))
        self._finish()

    def _tick(self) -> None:
        seconds = int(time.monotonic() - self._started)
        blocks = round(self._level / 20)
        self.setText(f"{seconds // 60}:{seconds % 60:02d}  " + "▰" * blocks + "▱" * (5 - blocks))
        if seconds >= MAX_SECONDS:
            self.stop()

    def _on_level(self, level: int) -> None:
        if self.state == "recording":
            self._level = level
            self._tick()

    def _recorded(self, path: str) -> None:
        if self.state == "idle":
            return
        started = self.page.services.transcribe(Path(path))
        if started is None:
            self._finish()
            return
        self._request, self._future = started

    def _record_error(self, text: str) -> None:
        log.warning("recording failed: %s", text)
        self._timer.stop()
        self._finish()
        self._toast(tr("The microphone could not be used: {error}", error=text), "bad")

    def _on_text(self, request_id: int, text: str) -> None:
        if request_id != self._request:
            return
        self._finish()
        if not text:
            self._toast(tr("No speech was heard. Speak a little louder or closer to the microphone."), "info")
            return
        cursor = self.target.textCursor()
        before = self.target.toPlainText()[: cursor.position()]
        cursor.insertText((" " if before and not before[-1].isspace() else "") + text)
        self.target.setTextCursor(cursor)
        self.target.setFocus()

    def _on_failed(self, request_id: int, code: str, _detail: str) -> None:
        if request_id == self._request:
            self._finish()
            self._toast(messages.engine_error(code), "bad")

    def _finish(self) -> None:
        self._request = 0
        self._future = None
        if self._file is not None:
            self._file.unlink(missing_ok=True)
            self._file = None
        self._show("idle")
