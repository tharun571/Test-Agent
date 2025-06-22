import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Pattern
import difflib
import ast
import astunparse

@dataclass
class ErrorAnalysis:
    """Analysis of a test error"""
    error_type: str
    error_message: str
    error_location: Optional[Tuple[str, int]] = None
    suggested_fix: Optional[str] = None
    confidence: float = 0.0
    related_code: Optional[str] = None

class TestErrorAnalyzer:
    """Analyze test failures and suggest fixes"""
    
    # Common error patterns
    ERROR_PATTERNS = {
        'import_error': r"(ImportError|ModuleNotFoundError): (.*)",
        'assertion_error': r"AssertionError: (.*)",
        'attribute_error': r"AttributeError: (.*)",
        'type_error': r"TypeError: (.*)",
        'value_error': r"ValueError: (.*)",
        'key_error': r"KeyError: (.*)",
        'does_not_exist': r"DoesNotExist: (.*)",
        'validation_error': r"ValidationError: (.*)",
        'template_error': r"TemplateSyntaxError: (.*)",
        'database_error': r"(IntegrityError|DatabaseError|OperationalError): (.*)",
    }
    
    def __init__(self, test_code: str, error_output: str):
        self.test_code = test_code
        self.error_output = error_output
        self.error_lines = error_output.split('\n')
        self.parsed_code = self._parse_test_code()
    
    def analyze(self) -> ErrorAnalysis:
        """Analyze the error and return analysis"""
        # First try to match known error patterns
        for error_type, pattern in self.ERROR_PATTERNS.items():
            match = re.search(pattern, self.error_output, re.DOTALL)
            if match:
                return getattr(self, f'_handle_{error_type}')(match)
        
        # If no specific pattern matched, try generic analysis
        return self._generic_error_analysis()
    
    def _parse_test_code(self) -> Optional[ast.AST]:
        """Parse the test code into an AST"""
        try:
            return ast.parse(self.test_code)
        except SyntaxError as e:
            return None
    
    def _handle_import_error(self, match: re.Match) -> ErrorAnalysis:
        """Handle import errors"""
        error_msg = match.group(2)
        module_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
        
        if module_match:
            module = module_match.group(1)
            return ErrorAnalysis(
                error_type="import_error",
                error_message=f"Missing module: {module}",
                suggested_fix=f"Add '{module}' to your requirements.txt or install it with pip",
                confidence=0.9
            )
        return self._generic_error_analysis()
    
    def _handle_assertion_error(self, match: re.Match) -> ErrorAnalysis:
        """Handle assertion errors"""
        error_msg = match.group(1)
        
        # Try to find the assertion in the test code
        assertion_line = None
        for i, line in enumerate(self.test_code.split('\n')):
            if 'assert ' in line:
                assertion_line = (i + 1, line.strip())
                break
        
        return ErrorAnalysis(
            error_type="assertion_error",
            error_message=f"Assertion failed: {error_msg}",
            error_location=("test", assertion_line[0]) if assertion_line else None,
            suggested_fix=f"Review the assertion on line {assertion_line[0]}: {assertion_line[1]}" if assertion_line else None,
            confidence=0.8
        )
    
    def _handle_attribute_error(self, match: re.Match) -> ErrorAnalysis:
        """Handle attribute errors"""
        error_msg = match.group(1)
        attr_match = re.search(r"'(\w+)' object has no attribute '(\w+)'", error_msg)
        
        if attr_match:
            obj_type = attr_match.group(1)
            attr = attr_match.group(2)
            
            # Look for similar attributes in the code
            similar = []
            test_attrs = self._find_attributes_in_code()
            if test_attrs:
                similar = difflib.get_close_matches(attr, test_attrs, n=3, cutoff=0.6)
            
            suggestion = f"Check if '{attr}' is the correct attribute name for {obj_type}"
            if similar:
                suggestion += f". Did you mean: {', '.join(similar)}?"
            
            return ErrorAnalysis(
                error_type="attribute_error",
                error_message=error_msg,
                suggested_fix=suggestion,
                confidence=0.85
            )
        return self._generic_error_analysis()
    
    def _handle_validation_error(self, match: re.Match) -> ErrorAnalysis:
        """Handle Django validation errors"""
        error_msg = match.group(1)
        
        # Look for common validation issues
        if "This field cannot be blank" in error_msg:
            field = error_msg.split("'")[1]  # Extract field name from message
            return ErrorAnalysis(
                error_type="validation_error",
                error_message=error_msg,
                suggested_fix=f"The field '{field}' is required but was not provided. Ensure you're including it in your test data.",
                confidence=0.9
            )
        
        return ErrorAnalysis(
            error_type="validation_error",
            error_message=error_msg,
            suggested_fix="Review the validation constraints in your model and ensure your test data meets all requirements.",
            confidence=0.8
        )
    
    def _find_attributes_in_code(self) -> List[str]:
        """Find all attribute accesses in the test code"""
        if not self.parsed_code:
            return []
            
        attributes = set()
        
        class AttributeVisitor(ast.NodeVisitor):
            def visit_Attribute(self, node):
                attributes.add(node.attr)
                self.generic_visit(node)
        
        visitor = AttributeVisitor()
        visitor.visit(self.parsed_code)
        return list(attributes)
    
    def _generic_error_analysis(self) -> ErrorAnalysis:
        """Generic error analysis when no pattern matches"""
        # Try to extract the most relevant error message
        lines = [line for line in self.error_lines if line.strip() and not line.startswith(' ' * 4)]
        error_line = lines[-1] if lines else "Unknown error"
        
        return ErrorAnalysis(
            error_type="unknown_error",
            error_message=error_line[:500],  # Limit length
            suggested_fix="Review the error message and check the relevant code paths.",
            confidence=0.5
        )
    
    @staticmethod
    def suggest_test_improvements(test_code: str, error_analysis: 'ErrorAnalysis') -> str:
        """Suggest improvements for a test based on error analysis"""
        suggestions = []
        
        if error_analysis.error_type == 'assertion_error':
            suggestions.append("Consider adding more specific assertions or debugging output.")
        
        if 'fixture' in error_analysis.error_message.lower():
            suggestions.append("Ensure all required test fixtures are properly set up.")
        
        if 'database' in error_analysis.error_message.lower():
            suggestions.append("Check database setup and ensure test database is properly configured.")
        
        if not suggestions:
            suggestions.append("Review the test case and ensure it covers all edge cases.")
        
        return "\n".join(f"• {suggestion}" for suggestion in suggestions)
