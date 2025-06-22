import os
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from typing import Optional, Dict, Any

logger = structlog.get_logger()

class GeminiClient:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.conversation_history = []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate response with retry logic and context management
        
        Args:
            prompt: The prompt to send to the LLM
            context: Additional context to include in the prompt
            
        Returns:
            str: The generated Python code block from the response
        """
        try:
            full_prompt = self._build_prompt(prompt, context)
            if os.getenv("LLM_DEBUG") == "1":
                print("\n=== LLM REQUEST =====================================")
                print(f"Model: {self.model._model_name}")
                print(full_prompt[:2000])
                print("=== END REQUEST ====================================\n")
                
            response = await self.model.generate_content_async(full_prompt)
            response_text = response.text
            
            if os.getenv("LLM_DEBUG") == "1":
                print("\n=== LLM RESPONSE ====================================")
                print(response_text[:2000])
                print("=== END RESPONSE ===================================\n")
                
            logger.info("llm_generation", prompt_length=len(full_prompt), response_length=len(response_text))
            self.conversation_history.append({"prompt": prompt, "response": response_text})
            
            # Extract only the Python code block from the response
            code_block = self._extract_python_code(response_text)
            return code_block or response_text  # Fallback to full response if no code block found
            
        except Exception as e:
            logger.error("llm_error", error=str(e))
            raise

    def _extract_python_code(self, text: str) -> str:
        """Extract Python code block from markdown response
        
        Args:
            text: The raw response text from the LLM
            
        Returns:
            str: The extracted Python code block, or empty string if not found
        """
        # Look for code blocks marked with ```python or ```
        code_blocks = []
        in_code_block = False
        current_block = []
        
        for line in text.split('\n'):
            if line.strip().startswith('```python'):
                in_code_block = True
                current_block = []
                continue
            elif line.strip() == '```' and in_code_block:
                in_code_block = False
                if current_block:  # Only add non-empty blocks
                    code_blocks.append('\n'.join(current_block))
                continue
                
            if in_code_block:
                current_block.append(line)
        
        # If no python-marked blocks found, try unmarked code blocks
        if not code_blocks:
            in_code_block = False
            current_block = []
            
            for line in text.split('\n'):
                if line.strip() == '```':
                    if in_code_block and current_block:
                        code_blocks.append('\n'.join(current_block))
                    in_code_block = not in_code_block
                    current_block = []
                    continue
                    
                if in_code_block:
                    current_block.append(line)
        
        # Return the first non-empty code block, or empty string if none found
        return next((block for block in code_blocks if block.strip()), '')

    def _build_prompt(self, prompt: str, context: Optional[Dict[str, Any]]) -> str:
        """Build prompt with context and conversation history"""
        sections = []
        sections.append("You are an expert test generator for Django applications using pytest.")
        if self.conversation_history:
            sections.append("\nPrevious context:")
            for item in self.conversation_history[-3:]:
                sections.append(f"User: {item['prompt'][:100]}...")
                sections.append(f"Assistant: {item['response'][:100]}...")
        if context:
            sections.append(f"\nCurrent context:\n{context}")
        sections.append(f"\nCurrent request:\n{prompt}")
        return "\n".join(sections)

    def clear_history(self):
        """Clear conversation history for new session"""
        self.conversation_history = []
