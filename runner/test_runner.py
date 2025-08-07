import os
import re
import sys
import time
import json
import subprocess
import importlib.util
import logging
import ast
from typing import List, Dict, Any, Optional, Union, Tuple

# Configure logging
logger = logging.getLogger(__name__)

def install_package(package_name: str) -> bool:
    """Install a Python package using pip.
    
    Args:
        package_name: Name of the package to install
        
    Returns:
        bool: True if installation was successful, False otherwise
    """
    try:
        logger.info(f"Installing missing package: {package_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name], 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install {package_name}: {str(e)}")
        return False

def ensure_packages(packages: List[str]) -> bool:
    """Ensure all required packages are installed.
    
    Args:
        packages: List of package names to check/install
        
    Returns:
        bool: True if all packages are available, False otherwise
    """
    all_installed = True
    for package in packages:
        if importlib.util.find_spec(package.split('==')[0]) is None:
            logger.warning(f"Package {package} not found. Attempting to install...")
            if not install_package(package):
                all_installed = False
    return all_installed

# List of required packages with optional version specifiers
REQUIRED_PACKAGES = [
    'django',
    'pytest',
    'pytest-django',
    'django-widget-tweaks',
    'mixer',
    'coverage',
    'rich',
    'python-dotenv',
    'docker',
    'paramiko'
]

# Ensure all required packages are installed
if not ensure_packages(REQUIRED_PACKAGES):
    logger.error("Failed to install one or more required packages. Some features may not work correctly.")
    # Continue execution but log the warning
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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
logger = logging.getLogger(__name__)

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

class TestRunner:
    """Run tests with sandboxing, coverage analysis, and error reporting"""
    
    def __init__(
        self,
        project_path: Union[str, Path],
        use_sandbox: bool = True,
        max_workers: int = 4,
        coverage_threshold: int = 80,
        timeout: int = 300,
    ):
        """Initialize the test runner
        
        Args:
            project_path: Path to the Django project root
            use_sandbox: Whether to use Docker sandbox for isolation
            max_workers: Maximum number of parallel test workers
            coverage_threshold: Minimum coverage percentage to pass (0-100)
            timeout: Maximum test execution time in seconds
        """
        # First ensure all required packages are installed
        if not ensure_packages(REQUIRED_PACKAGES):
            logger.warning("Some required packages could not be installed automatically. "
                         "Some features may not work as expected.")
        
        self.project_path = Path(project_path).resolve()
        self.use_sandbox = use_sandbox
        self.max_workers = max_workers
        self.coverage_threshold = coverage_threshold
        self.timeout = timeout
        self.sandbox = None
        
        # Initialize sandbox only if needed and requested
        if use_sandbox:
            self._init_sandbox()
        
        # Setup temp directory for test files
        self.temp_dir = self.project_path / ".test_tmp"
        self.temp_dir.mkdir(exist_ok=True)
    
    def _init_sandbox(self):
        """Initialize sandbox if needed"""
        if not self.use_sandbox:
            return
            
        try:
            self.sandbox = DockerSandbox(
                project_path=self.project_path,
                config=SandboxConfig(
                    django_settings=self._detect_django_settings()
                )
            )
            
            # Validate Docker setup
            is_valid, message = self.sandbox.validate_docker_setup()
            if not is_valid:
                console.print(f"[yellow]Warning: {message}[/yellow]")
                if not Confirm.ask("Continue without sandboxing?", default=True):
                    sys.exit(1)
                self.use_sandbox = False
                
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to initialize sandbox: {e}[/yellow]")
            self.use_sandbox = False
    
    def _create_test_file(self, test_code: str, test_name: str) -> Path:
        """Create a temporary test file with the given test code
        
        Args:
            test_code: The test code to write to the file
            test_name: Name for the test (used in filename)
            
        Returns:
            Path to the created test file
        """
        # Create a unique subdirectory for the test run
        test_run_dir = self.temp_dir / f"{test_name}_{int(time.time())}"
        test_run_dir.mkdir(parents=True, exist_ok=True)

        # Create a safe filename from the test name
        safe_name = "".join(c if c.isalnum() else "_" for c in test_name)
        safe_name = safe_name.strip("_")
        
        # Create the test file
        test_file = test_run_dir / f"test_{safe_name}.py"
        
        # Write the test code to the file
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_code)
            
        return test_file
        
    def _detect_django_settings(self) -> str:
        """Detect Django settings module by looking for common patterns
        
        Returns:
            str: The detected Django settings module path, or empty string if not found
        """
        # First check for manage.py to find the project root
        manage_py = self.project_path / 'manage.py'
        if not manage_py.exists():
            # Look for manage.py in subdirectories (common in some project structures)
            for root, _, files in os.walk(self.project_path):
                if 'manage.py' in files:
                    manage_py = Path(root) / 'manage.py'
                    break
        
        # If we found manage.py, try to extract settings module from it
        if manage_py.exists():
            try:
                with open(manage_py, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for DJANGO_SETTINGS_MODULE or os.environ.setdefault pattern
                    match = re.search(
                        r'os\.environ\.setdefault\s*\(\s*["\']DJANGO_SETTINGS_MODULE["\']\s*,\s*["\']([^"\']+)["\']\s*\)',
                        content
                    )
                    if match:
                        return match.group(1)
            except Exception:
                pass
        
        # Check common settings file locations
        common_paths = [
            'settings.py',
            'settings/__init__.py',
            'settings/base.py',
            'config/settings.py',
            'config/settings/__init__.py',
            'project/settings.py',
            'django_project/settings.py'
        ]
        
        for path in common_paths:
            settings_file = self.project_path / path
            if settings_file.exists():
                # Convert file path to module path
                rel_path = settings_file.relative_to(self.project_path)
                module_path = str(rel_path).replace('\\', '.').replace('/', '.').replace('.py', '')
                if module_path.endswith('.__init__'):
                    module_path = module_path[:-9]
                return module_path
        
        # If we still haven't found it, try to find any file named settings.py
        for root, _, files in os.walk(self.project_path):
            if 'settings.py' in files:
                rel_path = Path(root).relative_to(self.project_path) / 'settings.py'
                module_path = str(rel_path).replace('\\', '.').replace('/', '.')[:-3]  # Remove .py
                return module_path
        
        return ''  # Return empty string if not found
    
    def validate_test(self, test_code: str) -> Optional[str]:
        """Validate the test code for basic syntax errors."""
        try:
            ast.parse(test_code)
            return None
        except SyntaxError as e:
            return f"Syntax error in generated test: {e}"

    async def run_test(
        self,
        test_code: str,
        test_name: str = "generated_test",
        with_coverage: bool = False,
        retries: int = 3,
    ) -> TestResult:
        """Run a single test with optional coverage and retries.
        
        Args:
            test_code: Python test code to execute
            test_name: Name for the test (used for reporting)
            with_coverage: Whether to collect coverage data
            retries: Number of times to retry a failed test
            
        Returns:
            TestResult with execution results
        """
        validation_error = self.validate_test(test_code)
        if validation_error:
            return TestResult(
                success=False,
                output="",
                error=validation_error,
                test_name=test_name,
            )

        for attempt in range(retries):
            start_time = time.time()
            test_file = self._create_test_file(test_code, f"{test_name}_attempt_{attempt}")
            
            try:
                if self.use_sandbox and self.sandbox:
                    result = await self._run_in_sandbox(test_file, test_name, with_coverage)
                    result.execution_mode = "sandbox"
                else:
                    result = await self._run_locally(test_file, test_name, with_coverage)
                    result.execution_mode = "local"
                
                result.duration = time.time() - start_time
                result.test_file = str(test_file)
                
                # Analyze errors if test failed
                if not result.success and result.error:
                    analyzer = TestErrorAnalyzer(test_code, result.error)
                    result.error_analysis = analyzer.analyze()
                    
                    # Suggest fixes for common issues
                    if result.error_analysis and result.error_analysis.error_type == 'import_error':
                        result.error_analysis.suggested_fix = self._suggest_import_fix(
                            result.error_analysis.error_message
                        )
                
                if result.success:
                    return result

                logger.info(f"Test failed on attempt {attempt + 1}/{retries}. Retrying in 2 seconds...")
                await asyncio.sleep(2)

            except asyncio.TimeoutError:
                return TestResult(
                    success=False,
                    output="",
                    error=f"Test timed out after {self.timeout} seconds",
                    duration=time.time() - start_time,
                    test_name=test_name,
                    execution_mode="sandbox" if (self.use_sandbox and self.sandbox) else "local"
                )
            except Exception as e:
                logger.exception("Test execution failed")
                return TestResult(
                    success=False,
                    output="",
                    error=f"Test execution failed: {str(e)}",
                    duration=time.time() - start_time,
                    test_name=test_name,
                    execution_mode="sandbox" if (self.use_sandbox and self.sandbox) else "local"
                )
            finally:
                # Clean up temporary files
                if test_file and test_file.parent.exists():
                    shutil.rmtree(test_file.parent)
                
                # Clean up coverage files
                for ext in ['.coverage', '.coverage.*', 'coverage.xml', 'htmlcov']:
                    for f in self.project_path.glob(f'**/{ext}'):
                        if f.is_file():
                            f.unlink()
                        elif f.is_dir():
                            shutil.rmtree(f, ignore_errors=True)
        
        return result # Return the last result after all retries
    
    async def _run_in_sandbox(
        self, test_file: Path, test_name: str, with_coverage: bool = False
    ) -> TestResult:
        """Run test in Docker sandbox with optional coverage
        
        Args:
            test_file: Path to the test file
            test_name: Name of the test
            with_coverage: Whether to collect coverage data
            
        Returns:
            TestResult with execution results
        """
        try:
            # Prepare test code with coverage if needed
            with open(test_file, 'r') as f:
                test_code = f.read()
            
            if with_coverage:
                test_code = self._inject_coverage_setup(test_code)
            
            # Run in sandbox
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.sandbox.run_test_in_sandbox(test_code, test_name)
            )
            
            # Parse coverage data if available
            coverage_data = None
            if with_coverage and result.output:
                coverage_data = self._parse_coverage_output(result.output)
            
            return TestResult(
                success=result.success,
                output=result.output,
                error=result.error,
                duration=result.duration or 0,
                coverage_data=coverage_data,
                resource_usage=result.resource_usage
            )
            
        except Exception as e:
            logger.error(f"Sandbox execution failed: {str(e)}")
            raise
            
    def _inject_coverage_setup(self, test_code: str) -> str:
        """Inject coverage setup code into test file"""
        coverage_setup = """
# Coverage setup
import os
import sys
import atexit
import coverage

# Initialize coverage
cov = coverage.Coverage(
    source=[os.path.join(os.getcwd(), 'your_app')],  # Adjust to your app name
    omit=['*/tests/*', '*/migrations/*', '*/__pycache__/*'],
    data_file=os.path.join(os.getcwd(), '.coverage')
)
cov.start()

# Register coverage cleanup
def save_coverage():
    cov.stop()
    cov.save()
    cov.html_report(directory='htmlcov')

atexit.register(save_coverage)

"""
        # Find the first non-import line to insert after imports
        lines = test_code.split('\n')
        insert_at = 0
        for i, line in enumerate(lines):
            if not line.strip().startswith(('import ', 'from ')):
                insert_at = i
                break
                
        lines.insert(insert_at, coverage_setup)
        return '\n'.join(lines)
    
    def _suggest_import_fix(self, error_message: str) -> str:
        """Generate a suggested fix for import errors
        
        Args:
            error_message: The error message from the import error
            
        Returns:
            str: Suggested fix or empty string if no specific suggestion
        """
        # Common Django import errors
        if "No module named 'django'" in error_message:
            return "Django is not installed. Install it with: pip install django"
            
        if "No module named 'pytest'" in error_message:
            return "pytest is not installed. Install it with: pip install pytest pytest-django"
            
        if "No module named 'widget_tweaks'" in error_message:
            return "django-widget-tweaks is not installed. Install it with: pip install django-widget-tweaks"
            
        if "No module named 'mixer'" in error_message:
            return "django-mixer is not installed. Install it with: pip install mixer"
            
        # Check for missing app in INSTALLED_APPS
        app_match = re.search(r"ModuleNotFoundError: No module named '([^']+)'", error_message)
        if app_match:
            module_name = app_match.group(1)
            return (
                f"Module '{module_name}' not found. This might be because the app is not in INSTALLED_APPS. "
                f"Add '{module_name.split('.')[0]}' to INSTALLED_APPS in your Django settings."
            )
            
        # Check for model import errors
        model_match = re.search(r"Cannot import name '([^']+)' from '([^']+)'", error_message)
        if model_match:
            model_name = model_match.group(1)
            module_name = model_match.group(2)
            return (
                f"Could not import '{model_name}' from '{module_name}'. "
                "This might be because the model doesn't exist or there's a circular import."
            )
            
        # Generic suggestion for other import errors
        if "ImportError" in error_message or "ModuleNotFoundError" in error_message:
            return (
                "Check that the module is installed and in your Python path. "
                "If this is a local module, ensure the directory containing it is in your PYTHONPATH."
            )
            
        return ""  # No specific suggestion
    
    def _setup_django_environment(self, env: Dict[str, str]) -> None:
        """Set up the Django environment variables
        
        Args:
            env: Environment variables dictionary to update
        """
        # Set Django settings module if not already set
        if 'DJANGO_SETTINGS_MODULE' not in env:
            # Try to detect Django settings module
            settings_module = self._detect_django_settings()
            if settings_module:
                env['DJANGO_SETTINGS_MODULE'] = settings_module
            
        # Add project to Python path if not already there
        project_root = str(self.project_path)
        python_path = env.get('PYTHONPATH', '').split(os.pathsep)
        if project_root not in python_path:
            python_path.insert(0, project_root)
            env['PYTHONPATH'] = os.pathsep.join(filter(None, python_path))
    
    async def _run_locally(
        self, test_file: Path, test_name: str, with_coverage: bool = False
    ) -> TestResult:
        """Run test in the current Python environment with optional coverage
        
        Args:
            test_file: Path to the test file
            test_name: Name of the test
            with_coverage: Whether to collect coverage data
            
        Returns:
            TestResult with execution results
        """
        try:
            # Set up environment
            env = os.environ.copy()
            self._setup_django_environment(env)
            
            # Prepare command
            cmd = [
                sys.executable,
                '-m', 'pytest',
                '--ds', env.get('DJANGO_SETTINGS_MODULE', 'settings'),
                str(test_file),
                '-v',
                '-p', 'no:warnings'  # Suppress warnings for cleaner output
            ]
            
            # Add coverage if requested
            if with_coverage:
                cmd = [
                    'coverage', 'run',
                    '--parallel-mode',
                    '--source=.',
                    '--omit=*/tests/*,*/migrations/*,*/__pycache__/*',
                    '--module', 'pytest',
                    '--ds', env.get('DJANGO_SETTINGS_MODULE', 'settings'),
                    str(test_file),
                    '-v',
                    '-p', 'no:warnings'
                ]
            
            # Run the test with timeout
            start_time = time.time()
            
            if platform.system() == 'Windows':
                # Windows doesn't support signal.SIGALRM
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.project_path),
                    env=env
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout
                    )
                    returncode = process.returncode
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    raise
            else:
                # Unix supports signal.SIGALRM
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.project_path),
                    env=env,
                    preexec_fn=os.setsid  # For process group killing
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout
                    )
                    returncode = process.returncode
                except asyncio.TimeoutError:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    await process.wait()
                    raise
            
            # Process results
            output = stdout.decode()
            error = stderr.decode()
            
            # Parse coverage data if available
            coverage_data = None
            if with_coverage:
                coverage_data = self._parse_coverage_output(output + '\n' + error)
            
            return TestResult(
                success=returncode == 0,
                output=output,
                error=error if returncode != 0 else None,
                duration=time.time() - start_time,
                coverage_data=coverage_data
            )
            
        except asyncio.TimeoutError:
            return TestResult(
                success=False,
                output="",
                error=f"Test execution timed out after {self.timeout} seconds"
            )
        except Exception as e:
            logger.exception("Local test execution failed")
            return TestResult(
                success=False,
                output="",
                error=f"Local test execution failed: {str(e)}"
            )

def display_test_result(result: TestResult, show_output: bool = True) -> None:
    """Display test results in a user-friendly way
    
    Args:
        result: TestResult to display
        show_output: Whether to show the full test output
    """
    console = Console()
    
    # Test status
    if result.success:
        status = "[green]✓ PASSED[/green]"
        if result.coverage_data and 'coverage' in result.coverage_data:
            cov = result.coverage_data['coverage']
            status += f" [dim]({cov}% coverage)[/dim]"
        console.print(f"\n{status}")
    else:
        console.print("\n[red]✗ FAILED[/red]")
    
    # Test metadata
    meta = []
    if result.test_name:
        meta.append(f"Test: {result.test_name}")
    if result.test_file:
        meta.append(f"File: {os.path.basename(result.test_file)}")
    if meta:
        console.print("  " + " | ".join(meta))
    
    # Duration and resources
    stats = [f"Duration: {result.duration:.2f}s"]
    if result.resource_usage:
        if 'memory_usage' in result.resource_usage:
            mem_mb = result.resource_usage['memory_usage'] / (1024 * 1024)
            stats.append(f"Memory: {mem_mb:.1f}MB")
        if 'cpu_percent' in result.resource_usage:
            stats.append(f"CPU: {result.resource_usage['cpu_percent']:.1f}%")
    console.print("  " + " | ".join(stats))
    
    # Error analysis
    if not result.success and result.error_analysis:
        console.print("\n[bold]Error Analysis:[/bold]")
        console.print(f"  [bold]Type:[/bold] {result.error_analysis.error_type}")
        console.print(f"  [bold]Message:[/bold] {result.error_analysis.error_message}")
        
        if result.error_analysis.suggested_fix:
            console.print("\n  [bold]Suggested Fix:[/bold]")
            for line in result.error_analysis.suggested_fix.split('\n'):
                console.print(f"    {line}")
    
    # Show test output if requested
    if show_output and result.output:
        console.print("\n[bold]Test Output:[/bold]")
        try:
            # Try to parse as JSON for API responses
            import json
            output = json.loads(result.output)
            console.print_json(data=output)
        except (json.JSONDecodeError, TypeError):
            # Fall back to plain text
            console.print(Syntax(
                result.output,
                "text",
                theme="monokai",
                line_numbers=False,
                word_wrap=True
            ))
    
    # Show coverage report if available
    if result.coverage_data:
        self._display_coverage_report(result.coverage_data)
    
    console.print("")  # Add trailing newline

async def run_test_interactive(
    project_path: str,
    test_code: str,
    test_name: str = "generated_test",
    use_sandbox: bool = True,
    with_coverage: bool = False,
    show_output: bool = True
) -> TestResult:
    """Run a test interactively with progress and rich output
    
    Args:
        project_path: Path to the project root
        test_code: Python test code to execute
        test_name: Name for the test (used in reporting)
        use_sandbox: Whether to use Docker sandbox
        with_coverage: Whether to collect coverage data
        show_output: Whether to display test output
        
    Returns:
        TestResult with execution results
    """
    console = Console()
    
    # Set up progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=20),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Running test '{test_name}'...",
            total=1
        )
        
        try:
            # Initialize test runner
            runner = TestRunner(project_path, use_sandbox=use_sandbox)
            
            # Run the test
            result = await runner.run_test(
                test_code,
                test_name=test_name,
                with_coverage=with_coverage
            )
            
            # Update progress
            progress.update(task, completed=1)
            
            # Display results
            display_test_result(result, show_output=show_output)
            
            return result
            
        except Exception as e:
            progress.stop()
            console.print(f"[red]Error running test: {str(e)}[/red]")
            if "Docker" in str(e) and "not running" in str(e).lower():
                console.print("\n[bold]Docker is not running.[/bold]")
                console.print("Please start Docker Desktop and try again, or use local execution.")
            raise

async def run_tests_from_spec(
    project_path: str,
    spec: str,
    test_codes: List[str],
    use_sandbox: bool = True,
    with_coverage: bool = False,
    max_workers: int = 4,
) -> List[TestResult]:
    """Run multiple tests from a specification with parallel execution
    
    Args:
        project_path: Path to the project root
        spec: Description of what's being tested
        test_codes: List of test code strings to execute
        use_sandbox: Whether to use Docker sandbox
        with_coverage: Whether to collect coverage data
        max_workers: Maximum number of parallel test workers
        
    Returns:
        List of TestResult objects for all tests
    """
    console = Console()
    console.print(f"\n[bold]Running tests for:[/bold] {spec}")
    
    # Initialize test runner
    runner = TestRunner(
        project_path,
        use_sandbox=use_sandbox,
        max_workers=max_workers
    )
    
    # Set up progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=20),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Running {len(test_codes)} tests...",
            total=len(test_codes)
        )
        
        # Track results
        results = []
        
        # Run tests in parallel
        semaphore = asyncio.Semaphore(max_workers)
        
        async def run_single_test(i: int, test_code: str) -> TestResult:
            async with semaphore:
                test_name = f"test_case_{i}"
                result = await runner.run_test(
                    test_code,
                    test_name=test_name,
                    with_coverage=with_coverage
                )
                progress.update(task, advance=1)
                return result
        
        # Schedule all tests
        tasks = [
            asyncio.create_task(run_single_test(i, test_code))
            for i, test_code in enumerate(test_codes, 1)
        ]
        
        # Wait for all tests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        results = [
            r if not isinstance(r, Exception) else 
            TestResult(
                success=False,
                output="",
                error=f"Test execution failed: {str(r)}",
                test_name=f"test_case_{i+1}"
            )
            for i, r in enumerate(results)
        ]
    
    # Print summary
    passed = sum(1 for r in results if r.success)
    console.print(f"\n[bold]Test Summary:[/bold] {passed} passed, {len(results) - passed} failed")
    
    # Show coverage summary if enabled
    if with_coverage:
        coverage_data = await runner.combine_coverage()
        if coverage_data:
            _display_coverage_summary(coverage_data)
    
    # Show failed tests
    failed_tests = [(i, r) for i, r in enumerate(results, 1) if not r.success]
    if failed_tests:
        console.print("\n[bold]Failed Tests:[/bold]")
        for i, result in failed_tests:
            error_msg = (
                result.error_analysis.error_message 
                if result.error_analysis 
                else (result.error or 'Unknown error')
            )
            console.print(f"  {i}. {error_msg}")
    
    return results
