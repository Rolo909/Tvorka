"""Run an approved shell command in the project and keep its process tree together."""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from tvorka.core import proc

OUTPUT_LIMIT = 20_000
# The bootstrap cannot launch the shell until the process has a Windows job object.
_START = ("import subprocess,sys\n"
          "if sys.stdin.buffer.read(1) == b'1':\n"
          "    raise SystemExit(subprocess.call(sys.argv[1], shell=True))")
_DANGER = re.compile(
    r"\b(rm|del|rmdir)\s+[-/]|\bremove-item\b|\b(format|shutdown|curl|wget|invoke-webrequest)\b"
    r"|\bgit\s+(commit|push|reset|clean)\b|\b(pip3?|npm|uv|winget)\s+(install|add)\b"
    r"|[<>|;&`\n]|\$\(|%[^%]+%|(?:^|[\s\"'=])(?:[a-z]:|[/\\]|~[/\\]|\.\.(?:[/\\]|\b))", re.I,
)


@dataclass(frozen=True)
class CommandResult:
    exit_code: int | None
    output: str
    timed_out: bool = False
    truncated: bool = False


def dangerous(command: str) -> bool:
    return bool(_DANGER.search(command))


def reusable(command: str) -> bool:
    # Compound commands and interpreters that execute inline code always need a fresh approval.
    return not dangerous(command) and bool(re.fullmatch(
        r"(?:pytest|ruff|python(?:3)?\s+-m\s+(?:pytest|unittest|ruff))"
        r"(?:\s+[\w./:-]+)*", command, re.I,
    ))


class _Output:
    def __init__(self) -> None:
        self.head = bytearray()
        self.tail = bytearray()
        self.size = 0

    def drain(self, stream: BinaryIO) -> None:
        half = OUTPUT_LIMIT // 2
        while chunk := stream.read(8192):
            self.size += len(chunk)
            split = max(0, half - len(self.head))
            self.head.extend(chunk[:split])
            self.tail = (self.tail + chunk[split:])[-half:]

    def result(self) -> tuple[str, bool]:
        clipped = self.size > OUTPUT_LIMIT
        middle = b"\n[... output omitted ...]\n" if clipped else b""
        raw = bytes(self.head + middle + self.tail)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp866" if os.name == "nt" and not clipped else "utf-8", errors="replace")
        return text, clipped


def run_command(command: str, cwd: Path, timeout_s: float = 120,
                cancelled: Callable[[], bool] = lambda: False) -> CommandResult:
    if cancelled():
        return CommandResult(None, "")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    windows = sys.platform == "win32"
    with subprocess.Popen(
        [sys.executable, "-I", "-c", _START, command] if windows else command,
        cwd=cwd, env=env, shell=not windows, start_new_session=not windows,
        stdin=subprocess.PIPE if windows else subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if windows else 0,
    ) as process:
        job = None
        reader = None
        timed_out = stopped = False
        try:
            if windows:
                job = proc.kill_with_parent(process)
                if not job:
                    raise OSError("Could not supervise the Windows command and its child processes")
                assert process.stdin is not None
                process.stdin.write(b"1")
                process.stdin.close()
            assert process.stdout is not None
            capture = _Output()
            reader = threading.Thread(target=capture.drain, args=(process.stdout,), daemon=True)
            reader.start()
            deadline = time.monotonic() + min(max(timeout_s, 0.01), 600)
            while process.poll() is None:
                stopped, timed_out = cancelled(), time.monotonic() >= deadline
                if stopped or timed_out:
                    break
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=0.10)
        finally:
            if job:
                proc.close_handle(job)
            elif windows:
                process.kill()
            else:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            if reader is not None:
                reader.join()
        output, clipped = capture.result()
        return CommandResult(None if timed_out or stopped else process.returncode, output, timed_out, clipped)


def git_status(cwd: Path) -> str:
    path = os.pathsep.join(entry for entry in os.get_exec_path() if Path(entry).is_absolute())
    command = shutil.which("git", path=path)
    if not command or Path(command).resolve().is_relative_to(cwd.resolve()):
        raise FileNotFoundError("Git executable was not found on the system path")
    args = [command, "--no-optional-locks", "-c", "core.fsmonitor=false", "status", "--short"]
    result = subprocess.run(args, cwd=cwd, capture_output=True, timeout=5, check=False)
    return result.stdout.decode("utf-8", errors="replace")[:OUTPUT_LIMIT] if result.returncode == 0 else ""
