"""
Test Agent Runner - A robust test execution environment with sandboxing and error analysis.

This package provides a safe and isolated environment for running Python tests,
with features like Docker sandboxing, error analysis, and rich output formatting.
"""

from .sandbox import DockerSandbox, SandboxConfig, SandboxResult
from .error_analyzer import TestErrorAnalyzer, ErrorAnalysis
from .test_runner import (
    BaseTestRunner,
    DjangoTestRunner,
    PytestTestRunner,
    NodeTestRunner,
    TestResult,
    run_test_interactive,
)

__all__ = [
    'DockerSandbox',
    'SandboxConfig',
    'SandboxResult',
    'TestErrorAnalyzer',
    'ErrorAnalysis',
    'BaseTestRunner',
    'DjangoTestRunner',
    'PytestTestRunner',
    'NodeTestRunner',
    'TestResult',
    'run_test_interactive',
]

__version__ = '0.1.0'
