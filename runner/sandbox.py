import docker
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import json
import structlog
import time
from dataclasses import dataclass
import tarfile
import io

logger = structlog.get_logger()

@dataclass
class SandboxConfig:
    """Configuration for sandbox environment"""
    image: str = "python:3.11-slim"
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    timeout: int = 30
    network_disabled: bool = False
    read_only_root: bool = True
    django_settings: Optional[str] = None

@dataclass
class SandboxResult:
    """Result from sandbox execution"""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: Optional[int] = None
    duration: Optional[float] = None
    resource_usage: Optional[Dict[str, Any]] = None

class DockerSandbox:
    """Execute tests in isolated Docker containers"""
    
    def __init__(self, project_path: str, config: Optional[SandboxConfig] = None):
        self.project_path = Path(project_path)
        self.config = config or SandboxConfig()
        self.client = None
        self._init_docker_client()
        
    def _init_docker_client(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            # Test connection
            self.client.ping()
            logger.info("docker_client_initialized")
        except docker.errors.DockerException as e:
            logger.error("docker_initialization_failed", error=str(e))
            raise RuntimeError(f"Failed to connect to Docker: {str(e)}")
    
    def run_test_in_sandbox(self, test_code: str, test_name: str = "test") -> SandboxResult:
        """Run test in isolated Docker container"""
        start_time = time.time()
        container = None
        
        try:
            # Prepare test environment
            test_archive = self._prepare_test_archive(test_code, test_name)
            
            # Create container
            container = self._create_container(test_archive)
            
            # Run test
            result = self._execute_test(container)
            
            # Get resource usage
            stats = container.stats(stream=False)
            result.resource_usage = self._parse_resource_stats(stats)
            
            result.duration = time.time() - start_time
            return result
            
        except Exception as e:
            logger.error("sandbox_execution_failed", error=str(e))
            return SandboxResult(
                success=False,
                output="",
                error=f"Sandbox execution failed: {str(e)}",
                duration=time.time() - start_time
            )
        finally:
            # Cleanup
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
    
    def validate_docker_setup(self) -> Tuple[bool, str]:
        """Validate Docker is properly set up"""
        issues = []
        
        try:
            # Check Docker daemon
            self.client.ping()
        except:
            issues.append("Docker daemon is not running")
            return False, "\n".join(issues)
        
        # Check if required image exists or can be pulled
        try:
            self.client.images.get(self.config.image)
        except docker.errors.ImageNotFound:
            try:
                logger.info("pulling_docker_image", image=self.config.image)
                self.client.images.pull(self.config.image)
            except:
                issues.append(f"Cannot pull Docker image: {self.config.image}")
        
        # Check available resources
        info = self.client.info()
        if info.get('MemTotal', 0) < 1073741824:  # Less than 1GB
            issues.append("Low system memory for Docker containers")
        
        return len(issues) == 0, "\n".join(issues)
    
    def _prepare_test_archive(self, test_code: str, test_name: str) -> bytes:
        """Prepare tar archive with test and project files"""
        tar_buffer = io.BytesIO()
        
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            # Add test file
            test_content = self._prepare_test_content(test_code)
            test_info = tarfile.TarInfo(name=f"tests/{test_name}.py")
            test_info.size = len(test_content.encode())
            test_info.mtime = time.time()
            tar.addfile(test_info, io.BytesIO(test_content.encode()))
            
            # Add runner script
            runner_script = self._create_runner_script(test_name)
            runner_info = tarfile.TarInfo(name="run_tests.py")
            runner_info.size = len(runner_script.encode())
            runner_info.mtime = time.time()
            runner_info.mode = 0o755
            tar.addfile(runner_info, io.BytesIO(runner_script.encode()))
            
            # Add requirements file
            requirements = self._get_requirements()
            req_info = tarfile.TarInfo(name="requirements.txt")
            req_info.size = len(requirements.encode())
            req_info.mtime = time.time()
            tar.addfile(req_info, io.BytesIO(requirements.encode()))
            
            # Add project files (read-only mount would be better for large projects)
            self._add_project_files(tar)
        
        tar_buffer.seek(0)
        return tar_buffer.read()
    
    def _prepare_test_content(self, test_code: str) -> str:
        """Prepare test content with proper Django setup"""
        setup_code = """
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '{settings}')

# Add project to path
sys.path.insert(0, '/app')

django.setup()

""".format(settings=self.config.django_settings or 'settings')
        
        # Ensure imports are at the top
        lines = test_code.split('\n')
        import_lines = []
        other_lines = []
        
        for line in lines:
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
            else:
                other_lines.append(line)
        
        return '\n'.join(import_lines) + '\n' + setup_code + '\n'.join(other_lines)
    
    def _create_runner_script(self, test_name: str) -> str:
        """Create test runner script"""
        return f"""#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

# Import test module
from tests.{test_name} import *

if __name__ == '__main__':
    unittest.main()
"""

    def _get_requirements(self) -> str:
        """Get requirements for test environment"""
        return """django>=3.2,<5.0
pytest>=7.0.0
pytest-django>=4.5.0
factory-boy>=3.2.0
"""

    def _add_project_files(self, tar: tarfile.TarFile):
        """Add project files to the archive"""
        exclude = ['__pycache__', '*.pyc', '*.pyo', '*.pyd', '.git', 'venv', 'env']
        
        for file_path in self.project_path.rglob('*'):
            if file_path.is_file() and not any(file_path.match(pattern) for pattern in exclude):
                try:
                    arcname = str(file_path.relative_to(self.project_path))
                    tar.add(file_path, arcname=arcname, recursive=False)
                except Exception as e:
                    logger.warning("failed_to_add_file", path=file_path, error=str(e))
    
    def _create_container(self, test_archive: bytes) -> docker.models.containers.Container:
        """Create and configure Docker container"""
        container = self.client.containers.create(
            image=self.config.image,
            command=["/app/run_tests.py"],
            working_dir="/app",
            mem_limit=self.config.memory_limit,
            cpu_quota=int(self.config.cpu_limit * 100000),
            network_disabled=self.config.network_disabled,
            read_only=self.config.read_only_root,
            environment={
                'PYTHONUNBUFFERED': '1',
                'PYTHONDONTWRITEBYTECODE': '1',
                'PYTHONPATH': '/app'
            },
            volumes={
                '/app': {'bind': '/app', 'mode': 'rw'}
            }
        )
        
        # Copy test files to container
        container.put_archive("/", test_archive)
        return container
    
    def _execute_test(self, container) -> SandboxResult:
        """Execute test in container and collect results"""
        container.start()
        
        try:
            # Wait for container to finish with timeout
            container.wait(timeout=self.config.timeout)
            
            # Get container logs
            logs = container.logs(stdout=True, stderr=True, stream=False).decode()
            
            # Get exit code
            exit_code = container.attrs['State']['ExitCode']
            
            return SandboxResult(
                success=exit_code == 0,
                output=logs,
                exit_code=exit_code
            )
            
        except Exception as e:
            return SandboxResult(
                success=False,
                output="",
                error=f"Test execution failed: {str(e)}",
                exit_code=-1
            )
    
    def _parse_resource_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Docker container resource statistics"""
        try:
            memory_stats = stats.get('memory_stats', {})
            cpu_stats = stats.get('cpu_stats', {})
            
            return {
                'memory_usage': memory_stats.get('usage', 0),
                'memory_limit': memory_stats.get('limit', 0),
                'cpu_usage': cpu_stats.get('cpu_usage', {}).get('total_usage', 0),
                'system_cpu_usage': cpu_stats.get('system_cpu_usage', 0),
                'online_cpus': cpu_stats.get('online_cpus', 0)
            }
        except Exception as e:
            logger.warning("failed_to_parse_stats", error=str(e))
            return {}

    def __del__(self):
        """Clean up Docker client on destruction"""
        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
            except:
                pass
