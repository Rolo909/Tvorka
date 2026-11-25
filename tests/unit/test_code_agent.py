from __future__ import annotations

import json
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

from tvorka.core.code.agent import AgentLoop, Decision, Event, Permissions, Reply
from tvorka.core.code.commands import dangerous, reusable, run_command
from tvorka.core.code.edit_blocks import code_files
from tvorka.core.code.repomap import repo_map
from tvorka.core.code.sessions import SessionStore
from tvorka.core.code.tools import Approval
from tvorka.core.code.workspace import Workspace


def call(name: str, arguments: dict[str, Any] | str, identifier: str = "call_1") -> dict[str, Any]:
    return {"id": identifier, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments) if isinstance(arguments, dict) else arguments,
    }}


def make_agent(tmp_path: Path, mode: str, complete: Callable, approve: Callable[[Approval], Decision],
               events: list[Event] | None = None) -> AgentLoop:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def test():\n    return 1\n", encoding="utf-8")
    workspace = Workspace(project)
    store = SessionStore(tmp_path / "data")
    session = store.load(workspace)
    session.mode, session.ctx = mode, 8192
    def emit(event: Event) -> None:
        if events is not None:
            events.append(event)

    return AgentLoop(workspace, store.checkpoints(workspace), session, complete, approve,
                     emit, lambda: None, Permissions())


def test_read_only_mode_rejects_a_write_even_if_model_requests_it(tmp_path: Path) -> None:
    def model(messages: list, params: dict, _live: bool) -> Reply:
        offered = [entry["function"]["name"] for entry in params["tools"]]
        assert "write_file" not in offered
        if messages[-1]["role"] == "user":
            return Reply("", [call("write_file", {"path": "main.py", "content": "change"})])
        assert messages[-1]["tool_call_id"] == "call_1"
        assert messages[-1]["content"] == "ERROR: unknown_tool"
        return Reply("The code returns 1.")

    def approve(_proposal: Approval) -> Decision:
        raise AssertionError("Read-only mode must not request permission to write")

    agent = make_agent(tmp_path, "question", model, approve)
    assert agent.run("What does this code do?") == "done"
    assert (agent.workspace.root / "main.py").read_text(encoding="utf-8").endswith("return 1\n")


def test_invalid_arguments_do_not_terminate_the_agent(tmp_path: Path) -> None:
    def model(messages: list, _params: dict, _live: bool) -> Reply:
        if messages[-1]["role"] == "user":
            return Reply("", [call("read_file", '{"path":')])
        assert messages[-1]["content"] == "ERROR: invalid_arguments"
        return Reply("Finished")

    agent = make_agent(tmp_path, "agent", model, lambda _proposal: Decision("reject"))
    assert agent.run("Read the code") == "done"


def test_duplicate_calls_stop_after_five_and_keep_the_system_prefix(tmp_path: Path) -> None:
    prefixes = []
    feedback = []

    def model(messages: list, _params: dict, _live: bool) -> Reply:
        prefixes.append(messages[0]["content"])
        feedback.append(messages[-1]["content"])
        return Reply("", [call("read_file", {"path": "main.py"}, str(len(prefixes)))])

    agent = make_agent(tmp_path, "agent", model, lambda _proposal: Decision("reject"))
    assert agent.run("Inspect the source") == "loop"
    assert len(prefixes) == 5 and len(set(prefixes)) == 1
    assert "repeating" in feedback[3]


def test_edits_recovers_plain_code_and_still_requires_approval(tmp_path: Path) -> None:
    def model(_messages: list, params: dict, _live: bool) -> Reply:
        if "response_format" not in params:
            return Reply("```python\ndef test():\n    return 2\n```")
        return Reply(json.dumps({"edits": [{"path": "main.py", "search": "    return 1\n",
                                          "replace": "    return 2\n"}]}))

    approvals = []

    def approve(proposal: Approval) -> Decision:
        approvals.append(proposal)
        return Decision("reject")

    agent = make_agent(tmp_path, "edit", model, approve)
    assert agent.run("Return 2", ("main.py",)) == "done"
    assert len(approvals) == 1 and "+    return 2" in approvals[0].detail
    assert (agent.workspace.root / "main.py").read_text(encoding="utf-8").endswith("return 1\n")


def test_context_summary_keeps_the_system_and_recent_tool_sequence(tmp_path: Path) -> None:
    def model(messages: list, params: dict, live: bool) -> Reply:
        if not live:
            assert params["max_tokens"] == 800
            return Reply("Summary of earlier work")
        assert messages[0]["content"] == "Stable project prompt"
        assert messages[1]["content"] == "Earlier work summary:\nSummary of earlier work"
        assert messages[-2]["tool_call_id"] == "last_read"
        return Reply("Completed")

    agent = make_agent(tmp_path, "agent", model, lambda _proposal: Decision("reject"))
    agent.session.messages.extend([
        {"role": "system", "content": "Stable project prompt"},
        *[{"role": "user", "content": "x" * 4300} for _ in range(5)],
        *[{"role": "assistant", "content": "Progress"} for _ in range(4)],
        {"role": "assistant", "content": "", "tool_calls": [call("read_file", {}, "last_read")]},
        {"role": "tool", "tool_call_id": "last_read", "content": "Latest file content"},
    ])

    assert agent.run("Continue") == "done"


def test_code_handoff_preserves_template_filenames() -> None:
    answer = ("```html\n<link rel=\"stylesheet\" href=\"style.css\">\n```\n"
              "```css\nbody { margin: 0; }\n```\n```python filename=tools/check.py\npass\n```")
    assert set(code_files(answer)) == {"index.html", "style.css", "tools/check.py"}


def test_repo_search_and_outline_respect_project_filters(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("# ordinary\ndef exact(x):\n    return x\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("def exact(secret):\n", encoding="utf-8")
    (tmp_path / "client.key").write_text("def exact(private):\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "file.py").write_text("def exact(y):\n", encoding="utf-8")
    workspace = Workspace(tmp_path)

    assert "main.py" in workspace.tree(folder=".")
    assert workspace.search(r"^def exact", "*.py") == [("main.py", 2, "def exact(x):")]
    outline = repo_map(workspace, 75)
    assert len(outline) <= 75 and "main.py: def exact(x)" in outline
    assert "ignored" not in outline and "client.key" not in outline and ".env" not in outline


def test_commands_collect_output_without_unbounded_capture(tmp_path: Path) -> None:
    script = tmp_path / "output.py"
    script.write_text('print("begin" + "a" * 30_000 + "end")', encoding="utf-8")
    args = [sys.executable, script.name]
    command = subprocess.list2cmdline(args) if sys.platform == "win32" else shlex.join(args)

    result = run_command(command, tmp_path)

    assert result.exit_code == 0 and result.truncated
    assert result.output.startswith("begin") and result.output.rstrip().endswith("end")
    assert "output omitted" in result.output


def test_command_timeout_stops_the_child_process(tmp_path: Path) -> None:
    script = tmp_path / "child.py"
    script.write_text("import subprocess, sys\nfrom pathlib import Path\n"
                      "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                      "Path('child.pid').write_text(str(child.pid))\nchild.wait()\n", encoding="utf-8")
    args = [sys.executable, script.name]
    command = subprocess.list2cmdline(args) if sys.platform == "win32" else shlex.join(args)

    result = run_command(command, tmp_path, timeout_s=1.5)

    pid = int((tmp_path / "child.pid").read_text(encoding="utf-8"))
    assert result.timed_out and result.exit_code is None
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_command_session_permission_only_supports_simple_check_commands() -> None:
    assert reusable("python -m pytest tests/test_main.py -q")
    assert not reusable('python -c "print(42)"')
    assert dangerous("git push") and dangerous("pytest ../outside")
    assert dangerous("pytest -q && echo second") and not reusable("pytest -q && echo second")
