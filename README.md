# Test Agent

A powerful AI-powered test authoring tool that generates and runs tests for Django, Flask, and Node.js applications using natural language descriptions.

## Features

- **AI-Powered Test Generation**: Generate test cases using natural language descriptions.
- **Multi-Framework Support**: Built for Django, Flask, and Node.js projects.
- **Interactive CLI**: A user-friendly and visually appealing command-line interface powered by `rich`.
- **Project Analysis**: Automatically detects project type and analyzes project structure to identify testable components.
- **Test Execution**: Run generated tests interactively.
- **Git Integration**: Clone remote git repositories for analysis.

## Prerequisites

- Python 3.10+
- Node.js (for Node.js projects)
- Git
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
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

### Analyze a Project

The agent will automatically detect the project type (Django, Flask, or Node.js) and provide a summary of the project.

**Analyze a local project:**
```bash
test-agent analyze --path /path/to/your/project
```

**Analyze a remote project from a git repository:**
```bash
test-agent analyze --repo https://github.com/user/repo.git
```

If the provided path does not exist, the tool will output a clear error message:
```
Error: Path '/path/to/non-existent-project' does not exist.
```

### Generate and Run Tests

After analyzing a project, you can enter an interactive session to generate and run tests.

1.  Run the `analyze` command as shown above.
2.  When prompted, confirm that you want to generate tests.
3.  Follow the interactive prompts to provide test specifications in natural language.
4.  The agent will generate the test code and ask for confirmation to run it.

## Project Structure

```
Test-Agent/
├── agent/                  # AI agent and LLM integration
│   ├── __init__.py
│   ├── llm_client.py       # Gemini AI client
│   └── prompts.py          # Prompt templates
├── analyzer/               # Code analysis components
│   ├── __init__.py
│   ├── base_analyzer.py
│   ├── django_analyzer.py
│   ├── flask_analyzer.py
│   └── node_analyzer.py
├── cli/                    # Command-line interface
│   ├── __init__.py
│   └── main.py             # Main CLI implementation
├── runner/                 # Test execution
│   ├── __init__.py
│   └── test_runner.py      # Test runner
├── tests/                  # Test suite for the agent
│   ├── __init__.py
│   └── test_cli.py
├── .gitignore
├── README.md
├── requirements.txt
└── setup.py
```