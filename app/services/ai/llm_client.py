"""
DeepSeek LLM Integration Service for FastAPI application.
Provides async OpenAI client integration with DeepSeek API for specification extraction and comparison.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, Optional, Union
from pathlib import Path

import httpx
import yaml
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM Client for DeepSeek API integration with JSON Schema enforcement."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None
    ):
        """
        Initialize LLM client for DeepSeek API.
        
        Args:
            api_key: DeepSeek API key
            base_url: API base URL (defaults to config or "https://api.deepseek.com")
            model: Model name (defaults to config or "deepseek-chat")
            config_path: Path to YAML configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Set API parameters from config or arguments
        deepseek_config = self.config.get("deepseek", {})
        self.api_key = api_key or deepseek_config.get("api_key")
        self.base_url = base_url or deepseek_config.get("base_url", "https://api.deepseek.com")
        self.model = model or deepseek_config.get("model", "deepseek-chat")
        
        # Model parameters
        self.temperature = deepseek_config.get("temperature", 0.1)
        self.max_tokens = deepseek_config.get("max_tokens", 4000)
        self.top_p = deepseek_config.get("top_p", 0.95)
        self.frequency_penalty = deepseek_config.get("frequency_penalty", 0.0)
        self.presence_penalty = deepseek_config.get("presence_penalty", 0.0)
        
        # Request settings
        self.timeout = deepseek_config.get("timeout", 30)
        self.max_retries = deepseek_config.get("max_retries", 3)
        self.retry_delay = deepseek_config.get("retry_delay", 2)
        
        # Initialize async OpenAI client (DeepSeek is compatible with OpenAI API)
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout)
        )
        
        # Load prompt templates
        self.prompts = self.config.get("prompts", {})
        
        # Setup logging
        self.setup_logging()
        
        if not self.api_key:
            logger.warning("DeepSeek API key not provided. Client will not be able to make API calls.")
    
    def _load_config(self, config_path: Optional[Union[str, Path]]) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        default_config = {
            "deepseek": {
                "api_key": None,
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "temperature": 0.1,
                "max_tokens": 4000,
                "top_p": 0.95,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 2,
            },
            "prompts": {},
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
        
        # Try to load from provided path
        if config_path:
            try:
                config_path = Path(config_path)
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        loaded_config = yaml.safe_load(f)
                        return self._merge_dicts(default_config, loaded_config)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        # Try to load from default location
        default_config_path = Path("config.yaml")
        if default_config_path.exists():
            try:
                with open(default_config_path, 'r') as f:
                    loaded_config = yaml.safe_load(f)
                    return self._merge_dicts(default_config, loaded_config)
            except Exception as e:
                logger.warning(f"Failed to load config from default location: {e}")
        
        return default_config
    
    def _merge_dicts(self, dict1: Dict, dict2: Dict) -> Dict:
        """Recursively merge two dictionaries."""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging_config = self.config.get("logging", {})
        level = logging_config.get("level", "INFO")
        format_str = logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format=format_str
        )
    
    def _extract_json_from_text(self, text: str) -> str:
        """
        Extract JSON from text using regex patterns.
        Handles cases where LLM returns text with JSON embedded.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Extracted JSON string
        """
        # Common JSON patterns
        json_patterns = [
            r'```json\s*(.*?)\s*```',  # JSON code blocks
            r'```\s*(.*?)\s*```',      # Generic code blocks
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                # Return the longest match (most likely the actual JSON)
                return max(matches, key=len)
        
        # Try to find JSON object or array at the start/end of text
        # Look for JSON object { ... }
        json_obj_match = re.search(r'^\s*(\{.*\})\s*$', text, re.DOTALL)
        if json_obj_match:
            return json_obj_match.group(1)
        
        # Look for JSON array [ ... ]
        json_array_match = re.search(r'^\s*(\[.*\])\s*$', text, re.DOTALL)
        if json_array_match:
            return json_array_match.group(1)
        
        # Try to find any JSON structure
        # Look for JSON arrays first (they contain objects)
        json_array_any_match = re.search(r'(\[(?:[^\[\]]|(?:\[[^\[\]]*\]))*\])', text, re.DOTALL)
        if json_array_any_match:
            return json_array_any_match.group(1)
        
        # Then look for JSON objects
        json_any_match = re.search(r'(\{(?:[^{}]|(?:\{[^{}]*\}))*\})', text, re.DOTALL)
        if json_any_match:
            return json_any_match.group(1)
        
        # If no pattern matches, return the original text
        return text
    
    def _repair_json(self, json_str: str) -> str:
        """
        Attempt to repair malformed JSON.
        
        Args:
            json_str: Potentially malformed JSON string
            
        Returns:
            Repaired JSON string
        """
        try:
            # First try to parse as-is
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error, attempting repair: {e}")
            
            # Common fixes
            repaired = json_str
            
            # Fix trailing commas
            repaired = re.sub(r',\s*}', '}', repaired)
            repaired = re.sub(r',\s*]', ']', repaired)
            
            # Fix missing quotes around keys - but be careful with already quoted keys
            # Only fix unquoted keys that look like identifiers
            repaired = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', repaired)
            
            # Fix single quotes to double quotes, but be careful with escaped quotes
            # First handle escaped single quotes
            repaired = re.sub(r"\\'", "__SINGLE_QUOTE__", repaired)
            # Then convert remaining single quotes to double quotes
            repaired = repaired.replace("'", '"')
            # Restore escaped single quotes
            repaired = repaired.replace("__SINGLE_QUOTE__", "'")
            
            # Fix unescaped quotes inside strings
            # This is complex, so we'll use a simpler approach
            # Try to parse after basic fixes
            try:
                json.loads(repaired)
                return repaired
            except json.JSONDecodeError as e2:
                logger.warning(f"First repair attempt failed: {e2}")
                
                # Try more aggressive repair: use ast.literal_eval for Python-like dicts
                try:
                    import ast
                    # Try to parse as Python literal
                    parsed = ast.literal_eval(repaired)
                    # Convert back to JSON
                    return json.dumps(parsed, ensure_ascii=False)
                except (SyntaxError, ValueError) as e3:
                    logger.error(f"Failed to repair JSON with ast.literal_eval: {e3}")
                    
                    # Last resort: try to extract JSON-like structure
                    # Remove any non-JSON text at beginning and end
                    repaired = re.sub(r'^[^{[]*', '', repaired)
                    repaired = re.sub(r'[^}\]]*$', '', repaired)
                    
                    try:
                        json.loads(repaired)
                        return repaired
                    except json.JSONDecodeError:
                        logger.error(f"Failed to repair JSON: {json_str[:200]}...")
                        raise
    
    async def _make_request(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Make async request to DeepSeek API with retry logic and logging.
        
        Args:
            messages: List of message dictionaries
            system_prompt: Optional system prompt to prepend
            **kwargs: Additional parameters for chat completion
            
        Returns:
            ChatCompletion response
        """
        if not self.api_key:
            raise ValueError("DeepSeek API key is not set. Please provide an API key.")
        
        # Prepare messages with optional system prompt
        final_messages = []
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(messages)
        
        # Prepare request parameters
        request_params = {
            "model": self.model,
            "messages": final_messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "top_p": kwargs.get("top_p", self.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.frequency_penalty),
            "presence_penalty": kwargs.get("presence_penalty", self.presence_penalty),
            "response_format": {"type": "json_object"}
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in request_params:
                request_params[key] = value
        
        # Log request for debugging
        debug_data = {
            "timestamp": time.time(),
            "request": {
                "model": request_params.get("model"),
                "messages": final_messages,
                "temperature": request_params.get("temperature"),
                "max_tokens": request_params.get("max_tokens"),
                "system_prompt": system_prompt
            }
        }
        
        logger.info(f"Making LLM request with model: {self.model}")
        logger.debug(f"Request messages: {final_messages}")
        
        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Making DeepSeek API request (attempt {attempt + 1}/{self.max_retries})")
                response = await self.client.chat.completions.create(**request_params)
                
                # Log response for debugging
                debug_data["response"] = {
                    "id": response.id,
                    "model": response.model,
                    "created": response.created,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        "total_tokens": response.usage.total_tokens if response.usage else None
                    } if response.usage else None,
                    "choices_count": len(response.choices),
                }
                
                # Log raw content (truncated for readability)
                raw_content = response.choices[0].message.content if response.choices else None
                if raw_content:
                    debug_data["response"]["raw_content_preview"] = raw_content[:200] + "..." if len(raw_content) > 200 else raw_content
                
                # Store debug data
                response.debug_data = debug_data
                
                # Log to file
                self._log_to_file(debug_data)
                
                return response
            except Exception as e:
                last_exception = e
                debug_data["error"] = {
                    "attempt": attempt + 1,
                    "error": str(e),
                    "type": type(e).__name__
                }
                logger.warning(f"DeepSeek API request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # If we get here, all retries failed
        debug_data["final_error"] = str(last_exception)
        self._log_to_file(debug_data)
        raise Exception(f"DeepSeek API request failed after {self.max_retries} attempts: {last_exception}")
    
    def _log_to_file(self, data: Dict[str, Any]):
        """Log debug data to file."""
        try:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / "llm_requests.log"
            with open(log_file, "a") as f:
                f.write(json.dumps(data, indent=2, ensure_ascii=False))
                f.write("\n" + "="*80 + "\n")
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")
    
    async def extract_specs_from_tz(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Extract technical specifications from technical documentation text.
        
        Args:
            text: Raw text from technical documentation
            **kwargs: Additional parameters for the API request
            
        Returns:
            Dictionary containing extracted specifications
        """
        system_prompt = self.prompts.get("extract_specs_from_tz", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Extract technical specifications from the following technical documentation text:\n\n{text}"
            }
        ]
        
        response = await self._make_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        # Extract and repair JSON if needed
        json_str = self._extract_json_from_text(content)
        json_str = self._repair_json(json_str)
        
        # Parse JSON response
        try:
            result = json.loads(json_str)
            # Add debug data to result
            if hasattr(response, 'debug_data'):
                result["_debug"] = response.debug_data
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content[:500]}...")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    async def extract_specs_from_contract(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Extract specifications from contract document text.
        
        Args:
            text: Parsed contract document text
            **kwargs: Additional parameters for the API request
            
        Returns:
            Dictionary containing extracted contract specifications
        """
        system_prompt = self.prompts.get("extract_specs_from_contract_doc", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Extract technical specifications from the following contract document text:\n\n{text}"
            }
        ]
        
        response = await self._make_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        # Extract and repair JSON if needed
        json_str = self._extract_json_from_text(content)
        json_str = self._repair_json(json_str)
        
        # Parse JSON response
        try:
            result = json.loads(json_str)
            # Add debug data to result
            if hasattr(response, 'debug_data'):
                result["_debug"] = response.debug_data
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content[:500]}...")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    async def compare_specs(self, target_json: Dict[str, Any], contract_json: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Compare target specifications with contract specifications.
        
        Args:
            target_json: Target specifications dictionary
            contract_json: Contract specifications dictionary
            **kwargs: Additional parameters for the API request
            
        Returns:
            Dictionary containing comparison results with score and match type
        """
        system_prompt = self.prompts.get("compare_specs_and_score", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Compare the following target specifications with contract specifications:\n\n"
                          f"Target Specifications:\n{json.dumps(target_json, indent=2, ensure_ascii=False)}\n\n"
                          f"Contract Specifications:\n{json.dumps(contract_json, indent=2, ensure_ascii=False)}\n\n"
                          f"Calculate a match score from 0-100 and determine the match type."
            }
        ]
        
        response = await self._make_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        # Extract and repair JSON if needed
        json_str = self._extract_json_from_text(content)
        json_str = self._repair_json(json_str)
        
        # Parse JSON response
        try:
            result = json.loads(json_str)
            # Add debug data to result
            if hasattr(response, 'debug_data'):
                result["_debug"] = response.debug_data
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content[:500]}...")
            raise ValueError(f"Invalid JSON response from AI: {e}")


# Singleton instance for easy access
_llm_client_instance: Optional[LLMClient] = None


async def get_llm_client() -> LLMClient:
    """Get or create singleton LLMClient instance."""
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance


def set_llm_client(client: LLMClient) -> None:
    """Set the singleton LLMClient instance."""
    global _llm_client_instance
    _llm_client_instance = client