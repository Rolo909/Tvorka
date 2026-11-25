"""Tools offered to the local coding model and the proposals they can produce."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tvorka.core.code.workspace import Change, Workspace
from tvorka.core.llm.tools import Tool


@dataclass(frozen=True)
class Approval:
    kind: str
    label: str
    detail: str
    allow_session: bool = False


@dataclass(frozen=True)
class Outcome:
    text: str = ""
    change: Change | None = None
    command: str = ""
    timeout: int = 120
    image: dict[str, Any] = field(default_factory=dict)


def _tool(name: str, description: str, required: str, **properties: str) -> Tool:
    return Tool(name, description, {key: {"type": value} for key, value in properties.items()},
                tuple(required.split()))


READ = [
    _tool("list_files", "List files in the project or under a relative folder.", "", path="string"),
    _tool("read_file", "Read numbered lines of a text file at a project-relative path.", "path",
          path="string", start="integer", end="integer"),
    _tool("search", "Find a Python regular expression in project text files, optionally filtered by glob.",
          "pattern", pattern="string", glob="string"),
]
WRITE = [
    _tool("write_file", "Propose writing a text file at a project-relative path.", "path content",
          path="string", content="string"),
    _tool("edit_file", "Propose replacing exact existing text read from the file. Omit line numbers.",
          "path old_text new_text", path="string", old_text="string", new_text="string",
          replace_all="boolean"),
    _tool("delete_file", "Propose deleting a project text file. Requires confirmation.",
          "path", path="string"),
    _tool("run_command", "Propose a shell command to run in the project, with user confirmation.", "command",
          command="string", timeout_s="integer"),
    _tool("finish", "Finish the task with a short user-facing summary.", "summary", summary="string"),
]
IMAGE = _tool("generate_image", "Propose creating a new PNG asset through Tvorka's local image model.",
              "prompt path", prompt="string", path="string", width="integer", height="integer")


def code_tools(mode: str, image_ready: bool) -> dict[str, Tool]:
    tools = list(READ)
    if mode == "agent":
        tools.extend(WRITE)
        if image_ready:
            tools.append(IMAGE)
    return {tool.name: tool for tool in tools}


def propose(workspace: Workspace, name: str, args: dict[str, Any], check: Callable[[], None]) -> Outcome:
    match name:
        case "list_files":
            return Outcome("\n".join(workspace.tree(folder=args.get("path", ""), check=check)))
        case "read_file":
            return Outcome(workspace.read(args["path"], args.get("start", 1), args.get("end")))
        case "search":
            hits = workspace.search(args["pattern"], args.get("glob", ""), check=check)
            return Outcome("\n".join(f"{rel}:{line}: {text}" for rel, line, text in hits) or "No matches")
        case "write_file":
            return Outcome(change=workspace.propose_write(args["path"], args["content"]))
        case "edit_file":
            return Outcome(change=workspace.propose_edit(args["path"], args["old_text"], args["new_text"],
                                                         args.get("replace_all", False)))
        case "delete_file":
            return Outcome(change=workspace.propose_delete(args["path"]))
        case "run_command":
            return Outcome(command=args["command"], timeout=max(1, min(args.get("timeout_s", 120), 600)))
        case "generate_image":
            return Outcome(image=args)
        case "finish":
            return Outcome(args["summary"])
        case _:
            return Outcome("ERROR: unknown_tool")
