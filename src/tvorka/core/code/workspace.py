"""Read project files and apply explicitly selected text changes."""

from __future__ import annotations

import difflib
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath, PureWindowsPath

MAX_FILE_BYTES = 1024**2
MAX_READ_LINES = 400
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea",
             ".mypy_cache", ".pytest_cache"}
WINDOWS_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³]|conin\$|conout\$)(?:\.|$)", re.I)


class WorkspaceError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Change:
    path: str
    before: str | None
    after: str | None
    before_bytes: bytes | None
    encoding: str = "utf-8"
    newline: str = "\n"

    def replacement_bytes(self) -> bytes | None:
        if self.after is None:
            return None
        try:
            data = self.after.replace("\n", self.newline).encode(self.encoding)
        except UnicodeEncodeError as exc:
            raise WorkspaceError("encoding", self.path) from exc
        if len(data) > MAX_FILE_BYTES:
            raise WorkspaceError("too_large", self.path)
        return data

    def diff(self) -> str:
        lines = difflib.unified_diff(
            (self.before or "").splitlines(keepends=True), (self.after or "").splitlines(keepends=True),
            f"a/{self.path}" if self.before is not None else "/dev/null",
            f"b/{self.path}" if self.after is not None else "/dev/null",
        )
        return "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines
        )


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise WorkspaceError("outside", str(root))

    def resolve(self, rel: str) -> Path:
        path = PurePosixPath(rel.replace("\\", "/"))
        if path.is_absolute() or PureWindowsPath(rel).anchor or not path.parts:
            raise WorkspaceError("outside", rel)
        current = self.root
        for part in path.parts:
            key = part.casefold()
            if (part == ".." or key in {".git", ".env"} or key.startswith(".env.")
                    or part.endswith((" ", ".")) or WINDOWS_DEVICE.match(part)
                    or any(char in part for char in '<>:"|?*\x00')):
                raise WorkspaceError("outside", rel)
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError:
                continue
            reparse = getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            if stat.S_ISLNK(info.st_mode) or reparse:
                raise WorkspaceError("outside", rel)
        resolved = current.resolve()
        if not resolved.is_relative_to(self.root):
            raise WorkspaceError("outside", rel)
        return resolved

    def tree(self, max_entries: int = 400) -> list[str]:
        ignore = self.root / ".gitignore"
        patterns = []
        if ignore.is_file() and not ignore.is_symlink():
            with ignore.open(encoding="utf-8", errors="replace") as file:
                patterns = [p.strip(" /") for p in file.read(MAX_FILE_BYTES).splitlines()
                            if p.strip() and not p.lstrip().startswith(("#", "!"))]

        def hidden(rel: str, name: str) -> bool:
            return any(fnmatch(rel, pattern) or fnmatch(name, pattern) for pattern in patterns)

        paths = []
        total = 0
        for folder, dirs, files in os.walk(self.root):
            parent = Path(folder)
            dirs[:] = [name for name in sorted(dirs) if name.casefold() not in SKIP_DIRS
                       and not hidden((parent / name).relative_to(self.root).as_posix(), name)
                       and self._listed(parent / name)]
            for name in sorted(files):
                child = parent / name
                rel = child.relative_to(self.root).as_posix()
                if not hidden(rel, name) and self._listed(child):
                    total += 1
                    if len(paths) < max_entries:
                        paths.append(rel)
        paths.sort()
        if total > len(paths):
            paths.append(f"… и ещё {total - len(paths)} файлов")
        return paths

    def _listed(self, path: Path) -> bool:
        try:
            self.resolve(path.relative_to(self.root).as_posix())
        except (WorkspaceError, OSError):
            return False
        return True

    def read(self, rel: str, start: int = 1, end: int | None = None) -> str:
        before = self.propose_delete(rel).before or ""
        lines = before.splitlines()
        start = max(1, start)
        stop = min(len(lines), start + MAX_READ_LINES - 1, end if end is not None else len(lines))
        shown = [f"{number:4}| {lines[number - 1]}" for number in range(start, stop + 1)]
        if stop < len(lines) and start <= stop:
            shown.append(f"[показаны строки {start}–{stop} из {len(lines)}; следующие через start/end]")
        return "\n".join(shown)

    def snapshot(self, rel: str) -> bytes | None:
        return self._read_bytes(self.resolve(rel))

    def propose_write(self, rel: str, content: str) -> Change:
        path = self.resolve(rel)
        raw = self._read_bytes(path)
        if raw is None:
            return Change(path.relative_to(self.root).as_posix(), None, content, None)
        return self._change(path, raw, content)

    def propose_delete(self, rel: str) -> Change:
        path = self.resolve(rel)
        raw = self._read_bytes(path)
        if raw is None:
            raise WorkspaceError("not_found", rel)
        return self._change(path, raw, None)

    def propose_edit(self, rel: str, old: str, new: str, replace_all: bool = False) -> Change:
        current = self.propose_delete(rel)
        before = current.before or ""
        if not old:
            raise WorkspaceError("no_match", rel)
        hits = list(re.finditer(re.escape(old), before))
        if not hits and "\n" in old:
            pattern = r"[ \t]*\n".join(re.escape(line.rstrip(" \t")) for line in old.split("\n"))
            hits = list(re.finditer(pattern, before))
        if not hits:
            raise WorkspaceError("no_match", rel)
        if len(hits) > 1 and not replace_all:
            lines = ", ".join(str(before.count("\n", 0, hit.start()) + 1) for hit in hits)
            raise WorkspaceError("ambiguous", lines)
        last = 0
        parts = []
        for hit in hits:
            parts.extend((before[last:hit.start()], new))
            last = hit.end()
        parts.append(before[last:])
        return Change(current.path, before, "".join(parts),
                      current.before_bytes, current.encoding, current.newline)

    def apply(self, change: Change) -> None:
        self.replace_bytes(change.path, change.before_bytes, change.replacement_bytes())

    def replace_bytes(self, rel: str, expected: bytes | None, replacement: bytes | None) -> None:
        """Keep byte-for-byte snapshots for undo and validate their target just like ordinary edits."""
        path = self.resolve(rel)
        current = self.snapshot(rel)
        if current != expected:
            raise WorkspaceError("changed", rel)
        if replacement is None:
            if current is not None:
                path.unlink()
            return
        if len(replacement) > MAX_FILE_BYTES:
            raise WorkspaceError("too_large", rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.resolve(rel)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temp = Path(file.name)
            try:
                file.write(replacement)
                file.close()
                if self._read_bytes(self.resolve(rel)) != expected:
                    raise WorkspaceError("changed", rel)
                if expected is not None:
                    temp.chmod(stat.S_IMODE(path.stat().st_mode))
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)

    @staticmethod
    def _read_bytes(path: Path) -> bytes | None:
        try:
            if not stat.S_ISREG(path.stat().st_mode):
                raise WorkspaceError("outside", path.name)
            with path.open("rb") as file:
                data = file.read(MAX_FILE_BYTES + 1)
        except FileNotFoundError:
            return None
        if len(data) > MAX_FILE_BYTES:
            raise WorkspaceError("too_large", path.name)
        return data

    def _change(self, path: Path, raw: bytes, after: str | None) -> Change:
        rel = path.relative_to(self.root).as_posix()
        if b"\x00" in raw[:8192]:
            raise WorkspaceError("binary", rel)
        encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            before = raw.decode(encoding)
        except UnicodeDecodeError:
            encoding = "cp1251"
            try:
                before = raw.decode(encoding)
            except UnicodeDecodeError as exc:
                raise WorkspaceError("binary", rel) from exc
        newline = "\r\n" if b"\r\n" in raw else "\n"
        return Change(rel, before.replace("\r\n", "\n"), after, raw, encoding, newline)
