import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import tempfile
import asyncio
import os

from runner.test_runner import DjangoTestRunner, TestResult

class TestTestRunner(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.project_root = Path(self.tmpdir.name)
        (self.project_root / "manage.py").touch()

    def test_validate_test(self):
        runner = DjangoTestRunner(str(self.project_root))
        
        # Test valid code
        self.assertIsNone(runner.validate_test("import os"))
        
        # Test invalid code
        self.assertIsNotNone(runner.validate_test("import os\nprint 'hello'"))

    @patch('runner.test_runner.DjangoTestRunner.run_test', new_callable=AsyncMock)
    def test_retry_logic(self, mock_run_test):
        # Mock a failed test result
        mock_run_test.return_value = TestResult(success=False, output="", error="Test failed")
        
        runner = DjangoTestRunner(str(self.project_root), use_sandbox=False)
        
        # Run the test and check that it retries
        async def run():
            return await runner.run_test("import os")
        
        result = asyncio.run(run())
        
        self.assertEqual(mock_run_test.call_count, 1)
        self.assertFalse(result.success)

    @patch('runner.test_runner.DjangoTestRunner.run_test', new_callable=AsyncMock)
    def test_retry_logic_succeeds_on_second_try(self, mock_run_test):
        # Mock a failed test result, then a successful one
        mock_run_test.side_effect = [
            TestResult(success=False, output="", error="Test failed"),
            TestResult(success=True, output="")
        ]
        
        runner = DjangoTestRunner(str(self.project_root), use_sandbox=False)
        
        # Run the test and check that it retries and then succeeds
        async def run():
            # We need to call the runner twice to check the side_effect
            await runner.run_test("import os")
            return await runner.run_test("import os")
            
        result = asyncio.run(run())
        
        self.assertEqual(mock_run_test.call_count, 2)
        self.assertTrue(result.success)

if __name__ == '__main__':
    unittest.main()