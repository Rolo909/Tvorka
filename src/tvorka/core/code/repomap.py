"""A compact, read-only outline of a project's files and definitions."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

from tvorka.core.code.workspace import Workspace, WorkspaceError

_JS = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|const)\s+(\w+)", re.M)


def _symbols(workspace: Workspace, rel: str) -> list[str]:
    suffix = Path(rel).suffix.lower()
    if suffix not in {".py", ".js", ".ts", ".jsx", ".tsx"}:
        return []
    try:
        source = workspace.propose_delete(rel).before or ""
        if suffix == ".py":
            return [f"{'class' if isinstance(node, ast.ClassDef) else 'def'} {node.name}"
                    + (f"({', '.join(arg.arg for arg in node.args.args)})"
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "")
                    for node in ast.parse(source).body
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))][:8]
        return _JS.findall(source)[:8]
    except (WorkspaceError, OSError, SyntaxError, ValueError, RecursionError):
        return []


def repo_map(workspace: Workspace, budget_chars: int = 6000,
             check: Callable[[], None] = lambda: None) -> str:
    paths = sorted(workspace.tree(check=check), key=lambda rel: (rel.count("/"), rel))
    lines = []
    size = 0
    for rel in paths:
        if size + len(rel) + 1 > budget_chars:
            break
        lines.append(rel)
        size += len(rel) + 1
    for index, rel in enumerate(lines):
        check()
        names = _symbols(workspace, rel)
        if names:
            outline = ": " + ", ".join(names)
            if size + len(outline) <= budget_chars:
                lines[index] += outline
                size += len(outline)
    return "\n".join(lines)
