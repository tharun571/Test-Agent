import unittest
from pathlib import Path
import tempfile

from analyzer.flask_analyzer import FlaskAnalyzer

class TestFlaskAnalyzer(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.project_root = Path(self.tmpdir.name)

    def create_mock_file(self, path_str, content=""):
        path = self.project_root / path_str
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_analyze_flask_app(self):
        # Create a mock Flask app file
        self.create_mock_file(
            "app.py",
            "from flask import Flask\n\n"
            "app = Flask(__name__)\n\n"
            "@app.route('/')\n"
            "def home():\n"
            "    return 'Hello, World!'\n\n"
            "@app.route('/users/<user_id>', methods=['GET', 'POST'])\n"
            "def user_profile(user_id):\n"
            "    return f'User {user_id}'\n"
        )

        analyzer = FlaskAnalyzer(str(self.project_root))
        analyzer.analyze()

        # Check routes
        self.assertEqual(len(analyzer.routes), 2)
        
        # Check first route
        self.assertEqual(analyzer.routes[0]['path'], '/')
        self.assertEqual(analyzer.routes[0]['function'], 'home')
        
        # Check second route
        self.assertEqual(analyzer.routes[1]['path'], '/users/<user_id>')
        self.assertEqual(analyzer.routes[1]['function'], 'user_profile')

if __name__ == '__main__':
    unittest.main()
