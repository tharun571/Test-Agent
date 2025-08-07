"""Enhanced Django project analyzer (Phase 1 complete version).

Scans for Django files in arbitrary layouts and extracts models, views, URLs, and DRF serializers.
"""
import ast
import re
import structlog
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# File-system scan helpers
# ---------------------------------------------------------------------------

class DjangoFileScanner:
    """Locate Django-related files anywhere inside a project tree."""

    # filename patterns per category
    PATTERNS: Dict[str, List[str]] = {
        "models": ["models.py"],
        "views": ["views.py", "viewsets.py"],
        "urls": ["urls.py"],
        "serializers": ["serializers.py"],
    }

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

# ---------------------------------------------------------------------------
# Enhanced analyzer
# ---------------------------------------------------------------------------

class DjangoAnalyzer:
    """Analyze a Django project by AST-parsing discovered Django files."""

    def __init__(self, project_path: str):
        self.root = Path(project_path).resolve()
        self.scanner = DjangoFileScanner(project_path)
        self.models: Dict[str, List[Dict[str, Any]]] = {}
        self.views: Dict[str, List[Dict[str, Any]]] = {}
        self.urls: Dict[str, List[Dict[str, Any]]] = {}
        self.serializers: Dict[str, List[Dict[str, Any]]] = {}
        self.apps: Set[str] = set()

    def analyze(self):
        """Run full analysis."""
        logger.info("Starting Django project analysis...")
        self.scanner.scan()
        
        for file_path in self.scanner.files["models"]:
            self._parse_file(file_path, "models")
        for file_path in self.scanner.files["views"]:
            self._parse_file(file_path, "views")
        for file_path in self.scanner.files["urls"]:
            self._parse_file(file_path, "urls")
        for file_path in self.scanner.files["serializers"]:
            self._parse_file(file_path, "serializers")
        
        logger.info("Analysis complete.")

    def _parse_file(self, file_path: Path, category: str):
        """Read and AST-parse a single file."""
        app_name = self._get_app_name(file_path)
        self.apps.add(app_name)
        
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            
            if category == "models":
                if app_name not in self.models:
                    self.models[app_name] = []
                self.models[app_name].extend(self._extract_models(tree))
            elif category == "views":
                if app_name not in self.views:
                    self.views[app_name] = []
                self.views[app_name].extend(self._extract_views(tree))
            elif category == "urls":
                if app_name not in self.urls:
                    self.urls[app_name] = []
                self.urls[app_name].extend(self._extract_urls(tree))
            elif category == "serializers":
                if app_name not in self.serializers:
                    self.serializers[app_name] = []
                self.serializers[app_name].extend(self._extract_serializers(tree))

        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")

    def _get_app_name(self, file_path: Path) -> str:
        """Derive app name from file path."""
        return file_path.parent.name

    def _extract_models(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract model classes."""
        models = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Attribute) and base.attr == "Model":
                        models.append({"name": node.name, "fields": []})
                        break
        return models

    def _extract_views(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract view functions or classes."""
        views = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                views.append({"name": node.name, "type": "function"})
            elif isinstance(node, ast.ClassDef):
                views.append({"name": node.name, "type": "class"})
        return views

    def _extract_urls(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract url patterns."""
        urls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'path':
                if len(node.args) > 1:
                    pattern_node = node.args[0]
                    view_node = node.args[1]
                    
                    pattern = self._get_node_value(pattern_node)
                    view_name = self._get_node_value(view_node)
                    
                    if pattern and view_name:
                        urls.append({"pattern": pattern, "view": view_name})
        return urls

    def _extract_serializers(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract DRF serializers."""
        serializers = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Attribute) and "Serializer" in base.attr:
                        serializers.append({"name": node.name, "fields": []})
                        break
        return serializers

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

    def get_test_plan(self) -> Dict[str, Any]:
        """Generate a test plan from the analysis."""
        return {
            "models": self.models,
            "views": self.views,
            "urls": self.urls,
            "serializers": self.serializers,
            "endpoints": self._extract_testable_endpoints()
        }

    def _extract_testable_endpoints(self) -> List[Dict[str, Any]]:
        endpoints: List[Dict[str, Any]] = []
        for app_name in self.apps:
            for url in self.urls.get(app_name, []):
                endpoints.append({
                    "app": app_name,
                    "url": url["pattern"],
                    "view": url["view"],
                    "methods": ["GET", "POST", "PUT", "DELETE"],
                })
        return endpoints