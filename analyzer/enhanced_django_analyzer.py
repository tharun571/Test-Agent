"""Enhanced Django project analyzer.
Scans project directory recursively for Django-related files (models, views, urls, serializers)
and extracts light-weight metadata suitable for driving automated test generation.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------
class DjangoFileScanner:
    """Locate Django files inside a project tree without assumptions on layout."""

    PATTERNS: Dict[str, List[str]] = {
        "models": ["models.py"],
        "views": ["views.py", "viewsets.py"],
        "urls": ["urls.py"],
        "serializers": ["serializers.py"],
    }

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.files: Dict[str, List[Path]] = {k: [] for k in self.PATTERNS}

    def scan(self) -> None:
        skip = {".git", "__pycache__", "venv", ".venv", "env"}
        for py_file in self.root.rglob("*.py"):
            if any(part in skip for part in py_file.parts):
                continue
            for kind, patterns in self.PATTERNS.items():
                if py_file.name in patterns:
                    self.files[kind].append(py_file)
                    break

# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------
class DjangoAnalyzer:
    """Statically analyse a Django codebase to obtain a high-level structure map."""

    def __init__(self, project_path: str | Path):
        self.root = Path(project_path).resolve()
        self.scanner = DjangoFileScanner(self.root)
        self.models: Dict[str, List[Dict[str, Any]]] = {}
        self.views: Dict[str, List[Dict[str, Any]]] = {}
        self.urls: Dict[str, List[Dict[str, Any]]] = {}
        self.serializers: Dict[str, List[Dict[str, Any]]] = {}

    # Public -----------------------------------------------------------------
    def analyze(self) -> Dict[str, Any]:
        logger.info("analyse_start", project=str(self.root))
        self.scanner.scan()
        self._analyse_models()
        self._analyse_views()
        self._analyse_urls()
        self._analyse_serializers()
        return {
            "apps": sorted({p.parent.name for lst in self.scanner.files.values() for p in lst}),
            "models": self.models,
            "views": self.views,
            "urls": self.urls,
            "serializers": self.serializers,
            "testable_endpoints": self._build_endpoints(),
        }

    # Internal helpers -------------------------------------------------------
    def _app_name(self, file: Path) -> str:
        return file.parent.name

    # ---- models ------------------------------------------------------------
    def _analyse_models(self):
        for file in self.scanner.files["models"]:
            app = self._app_name(file)
            self.models.setdefault(app, []).extend(self._parse_models(file))

    def _parse_models(self, file: Path) -> List[Dict[str, Any]]:
        tree = ast.parse(file.read_text())
        out: List[Dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and self._is_model(node):
                out.append(
                    {
                        "name": node.name,
                        "file": str(file),
                        "fields": self._model_fields(node),
                    }
                )
        return out

    @staticmethod
    def _is_model(node: ast.ClassDef) -> bool:
        return any(
            (isinstance(base, ast.Attribute) and base.attr == "Model")
            or (isinstance(base, ast.Name) and base.id.endswith("Model"))
            for base in node.bases
        )

    @staticmethod
    def _model_fields(node: ast.ClassDef) -> List[str]:
        fields: List[str] = []
        for item in node.body:
            if isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name):
                        fields.append(t.id)
        return fields

    # ---- views -------------------------------------------------------------
    def _analyse_views(self):
        for file in self.scanner.files["views"]:
            app = self._app_name(file)
            self.views.setdefault(app, []).extend(self._parse_views(file))

    def _parse_views(self, file: Path) -> List[Dict[str, Any]]:
        tree = ast.parse(file.read_text())
        views: List[Dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.args.args and node.args.args[0].arg == "request":
                views.append({"name": node.name, "type": "function", "file": str(file)})
            elif isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id.endswith("View") for base in node.bases
            ):
                views.append({"name": node.name, "type": "class", "file": str(file)})
        return views

    # ---- urls --------------------------------------------------------------
    def _analyse_urls(self):
        regex = re.compile(r"path\s*\(\s*[r]?['\"](.*?)['\"]\s*,\s*([^,]+)")
        for file in self.scanner.files["urls"]:
            app = self._app_name(file)
            for url, view in regex.findall(file.read_text()):
                self.urls.setdefault(app, []).append({"pattern": url, "view": view.strip(), "file": str(file)})

    # ---- serializers -------------------------------------------------------
    def _analyse_serializers(self):
        for file in self.scanner.files["serializers"]:
            app = self._app_name(file)
            self.serializers.setdefault(app, []).append({"file": str(file)})

    # ---- endpoints ---------------------------------------------------------
    def _build_endpoints(self) -> List[Dict[str, Any]]:
        endpoints: List[Dict[str, Any]] = []
        for app, urls in self.urls.items():
            for info in urls:
                endpoints.append(
                    {
                        "app": app,
                        "url": info["pattern"],
                        "view": info["view"],
                        "methods": ["GET", "POST", "PUT", "DELETE"],
                    }
                )
        return endpoints
