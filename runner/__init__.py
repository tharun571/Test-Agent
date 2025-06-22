"""
Test Agent Runner - A robust test execution environment with sandboxing and error analysis.

This package provides a safe and isolated environment for running Python tests,
with features like Docker sandboxing, error analysis, and rich output formatting.
"""

from .sandbox import DockerSandbox, SandboxConfig, SandboxResult
from .error_analyzer import TestErrorAnalyzer, ErrorAnalysis
from .test_runner import TestRunner, TestResult, run_test_interactive, run_tests_from_spec

__all__ = [
    'DockerSandbox',
    'SandboxConfig',
    'SandboxResult',
    'TestErrorAnalyzer',
    'ErrorAnalysis',
    'TestRunner',
    'TestResult',
    'run_test_interactive',
    'run_tests_from_spec',
]

__version__ = '0.1.0'
