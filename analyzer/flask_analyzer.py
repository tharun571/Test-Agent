
"""Flask-specific project analyzer."""
import ast
from pathlib import Path
from typing import Dict, List, Any

import structlog

from analyzer.base_analyzer import FileScanner, BaseAnalyzer

logger = structlog.get_logger()


class FlaskFileScanner(FileScanner):
    """Locate Flask-related files."""

    PATTERNS: Dict[str, List[str]] = {
        "app": ["app.py", "main.py"],
    }


class FlaskAnalyzer(BaseAnalyzer):
    """Analyze a Flask project."""

    def __init__(self, project_path: str):
        super().__init__(project_path)
        self.scanner = FlaskFileScanner(project_path)
        self.routes: List[Dict[str, Any]] = []

    def analyze(self):
        """Run full analysis."""
        logger.info("Starting Flask project analysis...")
        self.scanner.scan()

        for file_path in self.scanner.files["app"]:
            self._parse_file(file_path, "app")

        logger.info("Analysis complete.")
        return {"routes": self.routes}

    def _parse_file(self, file_path: Path, category: str):
        """Read and AST-parse a single file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            self.routes.extend(self._extract_routes(tree))
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")

    def _extract_routes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract routes from @app.route decorators."""
        routes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if (isinstance(decorator, ast.Call) and
                            isinstance(decorator.func, ast.Attribute) and
                            decorator.func.attr == 'route'):
                        
                        methods = ["GET"]  # Default method
                        if decorator.args:
                            route_path = self._get_node_value(decorator.args[0])
                            
                            # Extract methods from keyword arguments
                            for keyword in decorator.keywords:
                                if keyword.arg == "methods":
                                    methods = [self._get_node_value(m) for m in keyword.value.elts]

                            routes.append({
                                "path": route_path,
                                "function": node.name,
                                "methods": methods
                            })
        return routes

    def get_test_plan(self) -> Dict[str, Any]:
        """Generate a test plan from the analysis."""
        return {
            "routes": self.routes,
        }
