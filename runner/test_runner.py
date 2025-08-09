import asyncio
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
import logging
import platform
import signal
import re
import os
import sys
import ast
import json
import time
import importlib.util

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn
)
from rich.prompt import Prompt, Confirm
from rich.traceback import Traceback

from .sandbox import DockerSandbox, SandboxResult, SandboxConfig
from .error_analyzer import TestErrorAnalyzer, ErrorAnalysis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()

@dataclass
class TestResult:
    """Results from running a test"""
    success: bool
    output: str
    error: Optional[str] = None
    duration: float = 0.0
    test_name: Optional[str] = None
    error_analysis: Optional[ErrorAnalysis] = None
    coverage_data: Optional[Dict[str, Any]] = None
    resource_usage: Optional[Dict[str, float]] = None
    test_file: Optional[str] = None
    execution_mode: str = "local"  # 'local' or 'sandbox'

class BaseTestRunner:
    """Base class for running tests."""
    def __init__(self, project_path: Union[str, Path], timeout: int = 300):
        self.project_path = Path(project_path).resolve()
        self.timeout = timeout
        self.temp_dir = self.project_path / ".test_tmp"
        self.temp_dir.mkdir(exist_ok=True)

    async def run_test(self, test_code: str, test_name: str, with_coverage: bool = False) -> TestResult:
        raise NotImplementedError

    def _create_test_file(self, test_code: str, test_name: str, extension: str) -> Path:
        test_run_dir = self.temp_dir / f"{test_name}_{int(time.time())}"
        test_run_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in test_name).strip("_")
        test_file = test_run_dir / f"test_{safe_name}{extension}"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_code)
        return test_file

    def validate_test(self, test_code: str) -> Optional[str]:
        """Validate the test code for basic syntax errors."""
        try:
            ast.parse(test_code)
            return None
        except SyntaxError as e:
            return f"Syntax error in generated test: {e}"

    def cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

class PytestTestRunner(BaseTestRunner):
    """A test runner for pytest-based projects (Flask, etc.)."""
    async def run_test(self, test_code: str, test_name: str, with_coverage: bool = False) -> TestResult:
        test_file = self._create_test_file(test_code, test_name, ".py")
        start_time = time.time()
        
        cmd = [sys.executable, '-m', 'pytest', str(test_file), '-v']
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_path)
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            
            output = stdout.decode()
            error = stderr.decode()
            
            return TestResult(
                success=process.returncode == 0,
                output=output,
                error=error if process.returncode != 0 else None,
                duration=time.time() - start_time,
                test_name=test_name,
                test_file=str(test_file)
            )
        except asyncio.TimeoutError:
            return TestResult(success=False, error="Test timed out.", duration=time.time() - start_time)
        finally:
            if test_file.parent.exists():
                shutil.rmtree(test_file.parent)

class NodeTestRunner(BaseTestRunner):
    """A test runner for Node.js projects (Jest)."""
    async def run_test(self, test_code: str, test_name: str, with_coverage: bool = False) -> TestResult:
        test_file = self._create_test_file(test_code, test_name, ".test.js")
        start_time = time.time()

        # Assuming jest is installed and configured
        cmd = ['npx', 'jest', str(test_file)]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_path)
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)

            output = stdout.decode()
            error = stderr.decode()

            return TestResult(
                success=process.returncode == 0,
                output=output,
                error=error if process.returncode != 0 else None,
                duration=time.time() - start_time,
                test_name=test_name,
                test_file=str(test_file)
            )
        except asyncio.TimeoutError:
            return TestResult(success=False, error="Test timed out.", duration=time.time() - start_time)
        except FileNotFoundError:
             return TestResult(success=False, error="`npx` command not found. Is Node.js installed and in your PATH?", duration=time.time() - start_time)
        finally:
            if test_file.parent.exists():
                shutil.rmtree(test_file.parent)


class DjangoTestRunner(PytestTestRunner):
    """The original TestRunner, now specifically for Django."""
    def __init__(
        self,
        project_path: Union[str, Path],
        use_sandbox: bool = True,
        max_workers: int = 4,
        coverage_threshold: int = 80,
        timeout: int = 300,
    ):
        super().__init__(project_path, timeout)
        self.use_sandbox = use_sandbox
        self.sandbox = None
        if use_sandbox:
            self._init_sandbox()

    def _init_sandbox(self):
        """Initialize sandbox if needed"""
        try:
            self.sandbox = DockerSandbox(
                project_path=self.project_path,
                config=SandboxConfig(
                    django_settings=self._detect_django_settings()
                )
            )
            is_valid, message = self.sandbox.validate_docker_setup()
            if not is_valid:
                console.print(f"[yellow]Warning: {message}[/yellow]")
                self.use_sandbox = False
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to initialize sandbox: {e}[/yellow]")
            self.use_sandbox = False

    def _detect_django_settings(self) -> str:
        manage_py = self.project_path / 'manage.py'
        if manage_py.exists():
            try:
                with open(manage_py, 'r', encoding='utf-8') as f:
                    content = f.read()
                    match = re.search(r'os.environ.setdefault\s*\(\s*["\\]\'DJANGO_SETTINGS_MODULE["\\]\'\s*,\s*["\\]([^"\\]+)["\\]\)\s*', content)
                    if match:
                        return match.group(1)
            except Exception:
                pass
        return ''

    async def run_test(
        self,
        test_code: str,
        test_name: str = "generated_test",
        with_coverage: bool = False,
    ) -> TestResult:
        test_file = self._create_test_file(test_code, test_name, ".py")
        start_time = time.time()
        
        env = os.environ.copy()
        settings_module = self._detect_django_settings()
        if settings_module:
            env['DJANGO_SETTINGS_MODULE'] = settings_module
        
        python_path = env.get('PYTHONPATH', '').split(os.pathsep)
        project_root = str(self.project_path)
        if project_root not in python_path:
            python_path.insert(0, project_root)
            env['PYTHONPATH'] = os.pathsep.join(filter(None, python_path))

        cmd = [
            sys.executable, '-m', 'pytest', 
            '--ds', env.get('DJANGO_SETTINGS_MODULE', 'settings'), 
            str(test_file), '-v'
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_path),
                env=env
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            
            output = stdout.decode()
            error = stderr.decode()
            
            return TestResult(
                success=process.returncode == 0,
                output=output,
                error=error if process.returncode != 0 else None,
                duration=time.time() - start_time,
                test_name=test_name,
                test_file=str(test_file)
            )
        except asyncio.TimeoutError:
            return TestResult(success=False, error="Test timed out.", duration=time.time() - start_time)
        finally:
            if test_file.parent.exists():
                shutil.rmtree(test_file.parent)


def get_test_runner(project_type: str, project_path: str) -> BaseTestRunner:
    if project_type == "django":
        return DjangoTestRunner(project_path)
    elif project_type == "flask":
        return PytestTestRunner(project_path)
    elif project_type == "node":
        return NodeTestRunner(project_path)
    else:
        raise ValueError(f"Unknown project type: {project_type}")

async def run_test_interactive(
    project_path: str,
    test_code: str,
    project_type: str,
    test_name: str = "generated_test",
    use_sandbox: bool = True,
    with_coverage: bool = False,
    show_output: bool = True
) -> TestResult:
    """Run a test interactively with progress and rich output"""
    runner = get_test_runner(project_type, project_path)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(f"[cyan]Running test '{test_name}'...", total=None)
        
        try:
            result = await runner.run_test(test_code, test_name, with_coverage)
            progress.stop()
            
            if result.success:
                console.print(f"\n[green]✓ PASSED[/green] ({result.duration:.2f}s)")
            else:
                console.print(f"\n[red]✗ FAILED[/red] ({result.duration:.2f}s)")
                if result.error:
                    console.print(Panel(result.error, title="Error", border_style="red"))

            if show_output and result.output:
                console.print(Panel(Syntax(result.output, "text", theme="monokai"), title="Output"))

            return result
        except Exception as e:
            progress.stop()
            console.print(f"[red]Error running test: {str(e)}[/red]")
            raise
        finally:
            runner.cleanup()
