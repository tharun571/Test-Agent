# Test Agent

A powerful AI-powered test authoring tool that generates and runs tests for Django applications using natural language descriptions.

## Features

- **AI-Powered Test Generation**: Generate test cases using natural language descriptions
- **Django Integration**: Built specifically for Django projects with support for models, views, and forms
- **Interactive CLI**: User-friendly command-line interface for test generation and execution
- **Error Analysis**: Automatic error detection and suggestions for fixes
- **Test Execution**: Run tests locally or in an isolated Docker sandbox
- **Coverage Reports**: Generate code coverage reports for your tests

## Prerequisites

- Python 3.8+
- Docker (optional, for sandboxed test execution)
- Google API Key (for Gemini AI integration)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Test-Agent
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root with your Google API key:
   ```
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage

### Analyze a Django Project

```bash
test-agent analyze --path /path/to/your/django/project
```

### Generate and Run Tests

1. Start an interactive test generation session:
   ```bash
   test-agent interactive --path /path/to/your/django/project
   ```

2. Follow the prompts to generate and run tests.

### Run Tests in Sandbox Mode

```bash
test-agent run --sandbox --path /path/to/your/django/project
```

### Generate Coverage Report

```bash
test-agent run --coverage --path /path/to/your/django/project
```

## Project Structure

```
Test-Agent/
├── agent/                  # AI agent and LLM integration
│   ├── __init__.py
│   ├── llm_client.py       # Gemini AI client
│   └── prompts.py          # Prompt templates
├── analyzer/               # Code analysis components
│   ├── __init__.py
│   ├── django_analyzer.py  # Django-specific analysis
│   └── enhanced_django_analyzer.py
├── cli/                    # Command-line interface
│   ├── __init__.py
│   └── main.py             # Main CLI implementation
├── runner/                 # Test execution
│   ├── __init__.py
│   ├── error_analyzer.py   # Error analysis
│   ├── sandbox.py          # Docker sandbox
│   └── test_runner.py      # Test runner
├── utils/                  # Utility functions
│   └── __init__.py
├── .env.example           # Example environment variables
├── requirements.txt       # Project dependencies
└── setup.py              # Package configuration
```

## Configuration

### Environment Variables

- `GOOGLE_API_KEY`: Your Google API key for Gemini AI
- `DJANGO_SETTINGS_MODULE`: Path to Django settings (optional)
- `PYTHONPATH`: Add project root to Python path if needed

### Project Settings

You can configure test generation behavior by creating a `.testagent` file in your project root:

```yaml
test_dir: "tests/generated"      # Where to save generated tests
default_imports: true           # Include default test imports
test_style: "pytest"            # pytest or unittest
coverage:
  source: "your_app"           # Source directory for coverage
  omit: ["*/migrations/*"]     # Files to exclude from coverage
```

## TODOs and Known Issues

### High Priority
- [ ] Fix Docker sandbox initialization
- [ ] Improve error handling for missing dependencies
- [ ] Add more comprehensive test coverage for the test runner
- [ ] Implement proper cleanup of temporary files and containers

### Medium Priority
- [ ] Add support for more test frameworks (e.g., pytest, unittest)
- [ ] Implement parallel test execution
- [ ] Add support for JavaScript/TypeScript testing
- [ ] Create VS Code/IntelliJ plugins for better IDE integration

### Low Priority
- [ ] Add support for other AI models (OpenAI, Anthropic, etc.)
- [ ] Implement a web-based UI for test generation
- [ ] Add support for CI/CD integration (GitHub Actions, GitLab CI, etc.)

## Example Usage

> **Example Project**: This tool is demonstrated using the [django-crud-ajax-login-register-fileupload](https://github.com/gowthamand/django-crud-ajax-login-register-fileupload) repository.

Here's an example of using the Test Agent to analyze a Django project and generate tests:

```bash
PS D:\SaaS\Test Agent> test-agent analyze --path ../app/app
C:\Users\athar\anaconda3\Lib\site-packages\paramiko\transport.py:219: CryptographyDeprecationWarning: Blowfish has been deprecated and will be removed in a future release
  "class": algorithms.Blowfish,
Package pytest-django not found. Attempting to install...
Package django-widget-tweaks not found. Attempting to install...
Package python-dotenv not found. Attempting to install...
🔍 Django Test Authoring Agent
Analyzing project structure...

2025-06-22 23:07:59 [info     ] analyse_start                  project=D:\SaaS\app\app
✓ Django project detected!
    Project Summary    
┏━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric      ┃ Count ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩
│ Apps        │ 2     │
│ Model files │ 4     │
│ View files  │ 18    │
│ URL files   │ 28    │
└─────────────┴───────┘
🎯 28 Testable Endpoints found
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ URL                  ┃ View              ┃ App  ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│                      │ views.index       │ crud │
│ create               │ views.create      │ crud │
│ list                 │ views.list        │ crud │
│ fileupload           │ views.fileupload  │ crud │
│ edit/<int:id>        │ views.edit        │ crud │
│ edit/update/<int:id> │ views.update      │ crud │
│ delete/<int:id>      │ views.delete      │ crud │
│ ajax/                │ views.ajax        │ crud │
│ ajax/ajax            │ views.ajax        │ crud │
│ ajax/delete          │ views.ajax_delete │ crud │
└──────────────────────┴───────────────────┴──────┘
... and 18 more

Would you like to generate tests? [y/n]: y

🧪 Interactive Test Generation Session

Enter test specification ('help' for commands): generate a failing test case for create under views.create
🤖 Generating test...
2025-06-22 23:08:53 [info     ] llm_generation                 prompt_length=16290 response_length=9181

✅ Generated Test:
import pytest
from django.urls import reverse
from crud.models import Member
from django.contrib.auth import get_user_model
from django.conf import settings
import datetime

# [Previous test code continues...]
```

This example shows the Test Agent analyzing a Django project, discovering testable endpoints, and generating failing test cases for the create view. The tool automatically installs missing dependencies and provides an interactive interface for test generation and execution.
