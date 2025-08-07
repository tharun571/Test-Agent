import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import tempfile
import asyncio
import os

from runner.test_runner import TestRunner, TestResult

class TestTestRunner(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.project_root = Path(self.tmpdir.name)
        (self.project_root / "manage.py").touch()

    def test_validate_test(self):
        runner = TestRunner(str(self.project_root))
        
        # Test valid code
        self.assertIsNone(runner.validate_test("import os"))
        
        # Test invalid code
        self.assertIsNotNone(runner.validate_test("import os\nprint 'hello'"))

    @patch('runner.test_runner.TestRunner._run_locally', new_callable=AsyncMock)
    def test_retry_logic(self, mock_run_locally):
        # Mock a failed test result
        mock_run_locally.return_value = TestResult(success=False, output="", error="Test failed")
        
        runner = TestRunner(str(self.project_root), use_sandbox=False)
        
        # Run the test and check that it retries
        async def run():
            return await runner.run_test("import os", retries=3)
        
        result = asyncio.run(run())
        
        self.assertEqual(mock_run_locally.call_count, 3)
        self.assertFalse(result.success)

    @patch('runner.test_runner.TestRunner._run_locally', new_callable=AsyncMock)
    def test_retry_logic_succeeds_on_second_try(self, mock_run_locally):
        # Mock a failed test result, then a successful one
        mock_run_locally.side_effect = [
            TestResult(success=False, output="", error="Test failed"),
            TestResult(success=True, output="")
        ]
        
        runner = TestRunner(str(self.project_root), use_sandbox=False)
        
        # Run the test and check that it retries and then succeeds
        async def run():
            return await runner.run_test("import os", retries=3)
            
        result = asyncio.run(run())
        
        self.assertEqual(mock_run_locally.call_count, 2)
        self.assertTrue(result.success)

    @patch('runner.test_runner.TestRunner._run_locally', new_callable=AsyncMock)
    def test_cleanup(self, mock_run_locally):
        # Mock a successful test result
        mock_run_locally.return_value = TestResult(success=True, output="")
        
        runner = TestRunner(str(self.project_root), use_sandbox=False)
        
        # Run the test
        async def run():
            return await runner.run_test("import os")
            
        result = asyncio.run(run())
        
        # Check that the temporary directory is cleaned up
        self.assertFalse(os.path.exists(Path(result.test_file).parent))

if __name__ == '__main__':
    unittest.main()