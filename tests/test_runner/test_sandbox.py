
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from runner.sandbox import DockerSandbox, SandboxConfig

class TestDockerSandbox(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.project_root = Path(self.tmpdir.name)
        (self.project_root / "manage.py").touch()

    @patch('runner.sandbox.docker')
    def test_create_container_security_features(self, mock_docker):
        # Mock the docker client
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        # Create a sandbox instance
        sandbox = DockerSandbox(str(self.project_root))

        # Call the method to be tested
        sandbox._create_container(b"test_archive")

        # Get the args and kwargs from the create call
        args, kwargs = mock_client.containers.create.call_args

        # Assert that the security features are enabled
        self.assertTrue(kwargs['network_disabled'])
        self.assertTrue(kwargs['read_only'])
        self.assertIn('/tmp', kwargs['tmpfs'])
        self.assertEqual(kwargs['volumes'][str(self.project_root)]['mode'], 'ro')

if __name__ == '__main__':
    unittest.main()
