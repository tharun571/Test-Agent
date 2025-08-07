
"""Base classes for code analysis."""
import ast
from pathlib import Path
from typing import Dict, List, Any, Set

import structlog

logger = structlog.get_logger()


class FileScanner:
    """Locate files of interest in a project tree."""

    PATTERNS: Dict[str, List[str]] = {}

    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        self.files: Dict[str, List[Path]] = {k: [] for k in self.PATTERNS}

    def scan(self):
        skip = {".git", "__pycache__", "venv", "env", ".venv"}
        for path in self.root.rglob("*.py"):
            if any(part in skip for part in path.parts):
                continue
            name = path.name.lower()
            for cat, patterns in self.PATTERNS.items():
                if name in patterns:
                    self.files[cat].append(path)
                    break


class BaseAnalyzer:
    """Base class for code analysis."""

    def __init__(self, project_path: str):
        self.root = Path(project_path).resolve()
        self.scanner = FileScanner(project_path)
        self.apps: Set[str] = set()

    def analyze(self):
        raise NotImplementedError

    def _parse_file(self, file_path: Path, category: str):
        raise NotImplementedError

    def _get_app_name(self, file_path: Path) -> str:
        """Derive app name from file path."""
        return file_path.parent.name

    def _get_node_value(self, node: ast.AST) -> str:
        """Safely extract value from AST node."""
        if isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_value(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""
