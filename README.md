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
