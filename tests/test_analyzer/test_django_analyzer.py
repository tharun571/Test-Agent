import unittest
from pathlib import Path
import tempfile
import os

from analyzer.django_analyzer import DjangoFileScanner, DjangoAnalyzer

class TestDjangoFileScanner(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.project_root = Path(self.tmpdir.name)

    def create_mock_file(self, path_str, content=""):
        path = self.project_root / path_str
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_scan(self):
        # Create mock files
        models_file = self.create_mock_file("app1/models.py")
        views_file = self.create_mock_file("app1/views.py")
        urls_file = self.create_mock_file("app2/urls.py")
        serializers_file = self.create_mock_file("app2/serializers.py")
        random_file = self.create_mock_file("app3/random.py")

        # Also create a file with a name that is a pattern but not an exact match
        self.create_mock_file("app3/my_models.py")


        scanner = DjangoFileScanner(str(self.project_root))
        scanner.scan()

        self.assertIn(models_file, scanner.files["models"])
        self.assertIn(views_file, scanner.files["views"])
        self.assertIn(urls_file, scanner.files["urls"])
        self.assertIn(serializers_file, scanner.files["serializers"])

        # Check that the random file is not in any category
        all_files = [file for files in scanner.files.values() for file in files]
        self.assertNotIn(random_file, all_files)
        self.assertEqual(len(all_files), 4)

class TestDjangoAnalyzer(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.project_root = Path(self.tmpdir.name)

    def create_mock_file(self, path_str, content=""):
        path = self.project_root / path_str
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_analyze(self):
        # Create mock project structure
        self.create_mock_file(
            "app1/models.py",
            "from django.db import models\n\n"
            "class MyModel(models.Model):\n"
            "    name = models.CharField(max_length=100)\n"
        )
        self.create_mock_file(
            "app1/views.py",
            "from django.http import HttpResponse\n\n"
            "def my_view(request):\n"
            "    return HttpResponse('hello')\n"
        )
        self.create_mock_file(
            "app1/urls.py",
            "from django.urls import path\n"
            "from . import views\n\n"
            "urlpatterns = [\n"
            "    path('my-view/', views.my_view, name='my-view'),\n"
            "]\n"
        )

        analyzer = DjangoAnalyzer(str(self.project_root))
        analyzer.analyze()

        # Check models
        self.assertIn("app1", analyzer.models)
        self.assertEqual(len(analyzer.models["app1"]),
                         1)
        self.assertEqual(analyzer.models["app1"][0]["name"], "MyModel")

        # Check views
        self.assertIn("app1", analyzer.views)
        self.assertEqual(len(analyzer.views["app1"]),
                         1)
        self.assertEqual(analyzer.views["app1"][0]["name"], "my_view")

        # Check URLs
        self.assertIn("app1", analyzer.urls)
        self.assertEqual(len(analyzer.urls["app1"]),
                         1)
        self.assertEqual(analyzer.urls["app1"][0]["pattern"], "my-view/")
        self.assertEqual(analyzer.urls["app1"][0]["view"], "views.my_view")


if __name__ == '__main__':
    unittest.main()