"""Prompt templates and context dataclasses for Phase 2 enhanced test generation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "TestContext",
    "PromptTemplates",
]


@dataclass
class TestContext:
    """Holds contextual information the LLM needs to generate a test."""

    specification: str
    target_type: str  # e.g. "endpoint", "model", "view", "function"
    target_info: Dict[str, Any]
    codebase_context: Dict[str, Any]
    previous_attempts: List[Dict[str, Any]] = field(default_factory=list)
    user_feedback: List[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Convert selected fields to a JSON string fed to the LLM."""
        return json.dumps(
            {
                "target_type": self.target_type,
                "target_info": self.target_info,
                "previous_attempts": len(self.previous_attempts),
                "has_feedback": bool(self.user_feedback),
            },
            indent=2,
        )


class PromptTemplates:
    """Central place for reusable prompt templates."""

    # ------------------------------------------------------------------
    # System / role prompts
    # ------------------------------------------------------------------
    SYSTEM_PROMPT_DJANGO = (
        "You are an expert Django test engineer specializing in pytest."" Your role is to generate high-quality, comprehensive tests based on natural language specifications.\n\n""
        "Key principles:\n"
        "1. Generate complete, runnable pytest code\n"
        "2. Include all necessary imports\n"
        "3. Use Django's test client appropriately\n"
        "4. Add helpful docstrings and comments\n"
        "5. Consider edge cases and error scenarios\n"
        "6. Follow Django testing best practices\n"
        "7. Use fixtures when appropriate\n"
        "8. Ensure tests are isolated and repeatable"
    )

    SYSTEM_PROMPT_FLASK = (
        "You are an expert Python test engineer specializing in testing Flask applications with pytest."" Your role is to generate high-quality, comprehensive tests based on natural language specifications.\n\n""
        "Key principles:\n"
        "1. Generate complete, runnable pytest code for Flask.\n"
        "2. Include all necessary imports.\n"
        "3. Use the Flask test client correctly (e.g., via a `client` fixture).\n"
        "4. Add helpful docstrings and comments.\n"
        "5. Consider edge cases and error scenarios.\n"
        "6. Follow Flask testing best practices.\n"
        "7. Use pytest fixtures for setup and teardown.\n"
        "8. Ensure tests are isolated and repeatable."
    )

    SYSTEM_PROMPT_NODE = (
        "You are an expert JavaScript/TypeScript test engineer specializing in testing Node.js applications, particularly those using the Express.js framework. You use Jest for testing."" Your role is to generate high-quality, comprehensive tests based on natural language specifications.\n\n""
        "Key principles:\n"
        "1. Generate complete, runnable Jest test code for Node.js/Express.js.\n"
        "2. Use `require` or `import` for modules as appropriate.\n"
        "3. Use a testing library like `supertest` to make HTTP requests to the application.\n"
        "4. Add helpful comments explaining the tests.\n"
        "5. Consider edge cases and error scenarios.\n"
        "6. Follow modern JavaScript/TypeScript testing best practices.\n"
        "7. Use `beforeEach`, `afterEach`, `beforeAll`, `afterAll` for setup and teardown.\n"
        "8. Ensure tests are isolated and repeatable."
    )

    # ------------------------------------------------------------------
    ANALYZE_SPECIFICATION = (
        "Analyze this test specification and extract key information:\n\n""
        "Specification: \"{specification}\"\n\n""
        "Context about the codebase:\n{codebase_context}\n\n""
        "Please identify:\n"
        "1. What is being tested (endpoint, model, function, etc.)\n"
        "2. The specific behavior or requirement to verify\n"
        "3. Input conditions or test data needed\n"
        "4. Expected outcomes or assertions\n"
        "5. Any edge cases mentioned or implied\n"
        "6. HTTP methods involved (for API tests)\n"
        "7. Authentication/permission requirements\n\n""
        "Provide a structured analysis in JSON format."
    )

    # ------------------------------------------------------------------
    GENERATE_MODEL_TEST = (
        "Generate a pytest test for a Django model based on this specification:\n\n""
        "Specification: \"{specification}\"\n\n""
        "Model Information:\n{model_info}\n\n""
        "Related Models:\n{related_models}\n\n""
        "Requirements:\n"
        "1. Test the specific behavior described\n"
        "2. Use appropriate Django model testing patterns\n"
        "3. Include necessary fixtures and test data\n"
        "4. Test both success and failure cases\n"
        "5. Add clear docstrings explaining what's being tested\n\n""
        "Generate complete, runnable pytest code."
    )

    # ------------------------------------------------------------------
    GENERATE_API_TEST_DJANGO = """You are an expert Django test engineer. Generate a comprehensive test for the specified endpoint.

IMPORTANT:
- If there is not enough context or the specification is unclear, DO NOT generate a test. Instead, respond with a clear message indicating what information is missing and what is required to proceed.
- Do NOT hallucinate endpoints, models, or behaviors that are not present in the provided context.
- Only use code elements that are explicitly present in the context or specification.

## Specification
{specification}

## Endpoint Details
- URL: {url_pattern}
- View: {view_name}
- Methods: {methods}
- Parameters: {parameters}

## Model Information
```json
{model_info}
```

## View Implementation
```python
{view_code}
```

## Test Requirements
1. Use Django's test client
2. Test both success and error cases
3. Include proper assertions for response status and data
4. Use model factories if available
5. Test field validation
6. Include docstrings explaining each test case

## Test Code
Generate a complete test file with all necessary imports and setup. If you cannot, explain why and do not generate code."""

    GENERATE_API_TEST_FLASK = """You are an expert Python test engineer for Flask applications. Generate a comprehensive test for the specified endpoint using pytest.

IMPORTANT:
- If there is not enough context or the specification is unclear, DO NOT generate a test. Instead, respond with a clear message indicating what information is missing and what is required to proceed.
- Do NOT hallucinate endpoints or behaviors that are not present in the provided context.
- Only use code elements that are explicitly present in the context or specification.

## Specification
{specification}

## Endpoint Details
- Path: {path}
- Function: {function}
- Methods: {methods}

## Application Context
```json
{app_context}
```

## Test Requirements
1. Use pytest and the Flask test client.
2. Create a pytest fixture for the Flask app (`app`) and client (`client`).
3. Test both success and error cases as described in the specification.
4. Include proper assertions for the response status code and data (e.g., `response.status_code`, `response.json()`).
5. Include docstrings explaining each test case.

## Test Code
Generate a complete test file with all necessary imports and setup. If you cannot, explain why and do not generate code."""

    GENERATE_API_TEST_NODE = """You are an expert JavaScript test engineer for Node.js applications. Generate a comprehensive test for the specified endpoint using Jest and supertest.

IMPORTANT:
- If there is not enough context or the specification is unclear, DO NOT generate a test. Instead, respond with a clear message indicating what information is missing and what is required to proceed.
- Do NOT hallucinate endpoints or behaviors that are not present in the provided context.
- Only use code elements that are explicitly present in the context or specification.

## Specification
{specification}

## Endpoint Details
- Path: {path}
- Handler: {handler}
- Methods: {methods}

## Application Context
```json
{app_context}
```

## Test Requirements
1. Use Jest for the test structure (`describe`, `it`, `expect`).
2. Use `supertest` to make HTTP requests to the Express app.
3. Assume the Express app is exported from `../{app_file}`. You will need to import it.
4. Test both success and error cases as described in the specification.
5. Include proper assertions for the response status code and body.
6. Your response should be a complete, runnable JavaScript file.

## Test Code
Generate a complete test file with all necessary imports and setup. If you cannot, explain why and do not generate code."""

