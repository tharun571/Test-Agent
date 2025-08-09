
"""Node.js-specific project analyzer."""
import ast
from pathlib import Path
from typing import Dict, List, Any
import json
import re

import structlog

from analyzer.base_analyzer import FileScanner, BaseAnalyzer

logger = structlog.get_logger()


class NodeFileScanner(FileScanner):
    """Locate Node.js-related files."""

    PATTERNS: Dict[str, list[str]] = {
        "app": ["index.js", "app.js", "server.js"],
        "routes": ["routes.js"],
    }


class NodeAnalyzer(BaseAnalyzer):
    """Analyze a Node.js project."""

    def __init__(self, project_path: str):
        super().__init__(project_path)
        self.scanner = NodeFileScanner(project_path)
        self.routes: list[dict[str, Any]] = []
        self.app_file: str = "app.js"

    def analyze(self) -> Dict[str, Any]:
        """Run full analysis."""
        logger.info("Starting Node.js project analysis...")
        
        # Find app file from package.json
        try:
            package_json_path = self.root / "package.json"
            if package_json_path.exists():
                with open(package_json_path, "r") as f:
                    package_data = json.load(f)
                    self.app_file = package_data.get("main", self.app_file)
        except Exception as e:
            logger.warning(f"Could not read package.json: {e}")

        self.scanner.scan()

        all_js_files = list(self.root.rglob("*.js"))
        for file_path in all_js_files:
            if "node_modules" in file_path.parts:
                continue
            self._parse_file(file_path)

        logger.info("Node.js analysis complete.")
        return {
            "routes": self.routes,
            "app_file": self.app_file,
        }

    def _parse_file(self, file_path: Path):
        """Read and parse a single JS file for routes."""
        try:
            content = file_path.read_text(encoding="utf-8")
            self.routes.extend(self._extract_routes(content))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")

    def _extract_routes(self, content: str) -> List[Dict[str, Any]]:
        """Extract routes from JS code using regex."""
        routes = []
        
        # Regex for app.get('/path', handler) or router.post('/path', handler)
        route_pattern = re.compile(
            r"""
            (?:app|router)\.
            (get|post|put|delete|patch|all) # HTTP method
            \s*\(\s*
            [`'"](.+?)['"`] # Route path
            \s*,\s*
            .* # Ignore middleware and handler
            \)
            """, re.VERBOSE)

        for match in route_pattern.finditer(content):
            method, path = match.groups()
            routes.append({
                "path": path,
                "methods": [method.upper()],
                "handler": "unknown",
            })
            
        return routes

    def get_test_plan(self) -> Dict[str, Any]:
        """Generate a test plan from the analysis."""
        return {
            "routes": self.routes,
            "app_file": self.app_file,
        }
