from pathlib import Path

import pytest

from tvorka.core.code.checkpoints import Checkpoints
from tvorka.core.code.edit_blocks import parse_blocks
from tvorka.core.code.workspace import Workspace, WorkspaceError


@pytest.mark.parametrize("name", ["../outside.txt", "C:/Windows/x", "/etc/x", "src/NUL.txt",
                                  ".git/config", ".env", "file.txt:stream"])
def test_workspace_rejects_paths_outside_edit_scope(tmp_path: Path, name: str) -> None:
    workspace = Workspace(tmp_path)
    with pytest.raises(WorkspaceError) as error:
        workspace.resolve(name)
    assert error.value.code == "outside"


def test_workspace_rejects_a_link_outside(tmp_path: Path) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    try:
        (folder / "link.txt").symlink_to(outside)
    except OSError:
        pytest.skip("creating a symbolic link requires permission on this OS")
    with pytest.raises(WorkspaceError) as error:
        Workspace(folder).resolve("link.txt")
    assert error.value.code == "outside"


@pytest.mark.parametrize(("encoding", "newline"),
                         [("utf-8-sig", "\r\n"), ("cp1251", "\r\n"), ("utf-8", "\n")])
def test_edit_preserves_encoding_and_line_endings(tmp_path: Path, encoding: str, newline: str) -> None:
    path = tmp_path / "file.txt"
    original = newline.join(["закат   ", "маяк", ""])
    path.write_bytes(original.encode(encoding))
    workspace = Workspace(tmp_path)

    change = workspace.propose_edit("file.txt", "закат\nмаяк\n", "вечер\nмаяк\n")
    assert path.read_bytes() == original.encode(encoding)
    assert "+вечер" in change.diff()
    workspace.apply(change)

    assert path.read_bytes() == newline.join(["вечер", "маяк", ""]).encode(encoding)


def test_edit_will_not_overwrite_external_changes(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("before")
    workspace = Workspace(tmp_path)
    change = workspace.propose_write("file.txt", "after")
    path.write_text("new changes")

    with pytest.raises(WorkspaceError) as error:
        workspace.apply(change)

    assert error.value.code == "changed" and path.read_text() == "new changes"


def test_tree_and_numbered_read_exclude_or_limit_files(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("secret")
    (tmp_path / ".gitignore").write_text("*.log")
    (tmp_path / "ignored.log").touch()
    (tmp_path / "lines.txt").write_text("line\n" * 501)
    workspace = Workspace(tmp_path)

    assert workspace.tree() == [".gitignore", "lines.txt"]
    read = workspace.read("lines.txt", 2)
    assert read.startswith("   2| line") and " 401| line" in read and " 402|" not in read


def test_parse_edit_blocks_inside_markdown_and_reject_truncated_block() -> None:
    text = "```text\napp.py\n<<<<<<< SEARCH  \nold\n=======\nnew\n>>>>>>> REPLACE\n```"
    [block] = parse_blocks(text)
    assert (block.path, block.search, block.replace) == ("app.py", "old\n", "new\n")
    with pytest.raises(WorkspaceError) as error:
        parse_blocks("app.py\n<<<<<<< SEARCH\nold\n")
    assert error.value.code == "bad_block"


def test_checkpoints_restore_edits_creation_and_deletion_byte_for_byte(tmp_path: Path) -> None:
    folder = tmp_path / "project"
    folder.mkdir()
    source = folder / "file.txt"
    original = "маяк\r\n".encode("utf-8-sig")
    source.write_bytes(original)
    workspace = Workspace(folder)
    history = Checkpoints(workspace, tmp_path / "session")
    history.apply(workspace.propose_write("file.txt", "later\n"))
    history.apply(workspace.propose_write("new.txt", "new\n"))
    history.apply(workspace.propose_delete("file.txt"))

    Checkpoints(workspace, history.folder).undo_to(0)

    assert source.read_bytes() == original
    assert not (folder / "new.txt").exists() and not history.undo_last()
