"""
DeepSeek AI Client for LLM-based text processing and analysis.
Provides a wrapper around DeepSeek API with proper error handling and response parsing.
"""

import json
import logging
import time
from typing import Any, Dict, Optional, Union
from pathlib import Path

import httpx
import yaml
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """Client for interacting with DeepSeek AI API."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        config_path: Optional[Union[str, Path]] = None
    ):
        """
        Initialize DeepSeek AI client.
        
        Args:
            api_key: DeepSeek API key (defaults to settings.DEEPSEEK_API_KEY)
            base_url: API base URL (defaults to settings.DEEPSEEK_BASE_URL)
            model: Model name (defaults to settings.DEEPSEEK_MODEL)
            config_path: Path to YAML configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Set API parameters
        self.api_key = api_key or settings.DEEPSEEK_API_KEY or self.config.get("deepseek", {}).get("api_key")
        self.base_url = base_url or settings.DEEPSEEK_BASE_URL or self.config.get("deepseek", {}).get("base_url")
        self.model = model or settings.DEEPSEEK_MODEL or self.config.get("deepseek", {}).get("model")
        
        # Model parameters from config
        deepseek_config = self.config.get("deepseek", {})
        self.temperature = deepseek_config.get("temperature", 0.1)
        self.max_tokens = deepseek_config.get("max_tokens", 4000)
        self.top_p = deepseek_config.get("top_p", 0.95)
        self.frequency_penalty = deepseek_config.get("frequency_penalty", 0.0)
        self.presence_penalty = deepseek_config.get("presence_penalty", 0.0)
        
        # Request settings
        self.timeout = deepseek_config.get("timeout", 30)
        self.max_retries = deepseek_config.get("max_retries", 3)
        self.retry_delay = deepseek_config.get("retry_delay", 2)
        
        # Initialize OpenAI client (DeepSeek is compatible with OpenAI API)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout)
        )
        
        self.async_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout)
        )
        
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
                "response_format": {"type": "json_object"}
            }
        }
        
        if config_path:
            try:
                config_path = Path(config_path)
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        loaded_config = yaml.safe_load(f)
                        # Merge with default config
                        merged_config = self._merge_dicts(default_config, loaded_config)
                        return merged_config
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        # Try to load from default location
        default_config_path = Path("config.yaml")
        if default_config_path.exists():
            try:
                with open(default_config_path, 'r') as f:
                    loaded_config = yaml.safe_load(f)
                    merged_config = self._merge_dicts(default_config, loaded_config)
                    return merged_config
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
    
    def _make_request(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatCompletion:
        """
        Make a request to DeepSeek API with retry logic.
        
        Args:
            messages: List of message dictionaries
            system_prompt: Optional system prompt to prepend
            **kwargs: Additional parameters for chat completion
            
        Returns:
            ChatCompletion response
            
        Raises:
            ValueError: If API key is not set
            Exception: If API request fails after retries
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
            "response_format": {"type": "json_object"}  # Always request JSON
        }
        
        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in request_params:
                request_params[key] = value
        
        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Making DeepSeek API request (attempt {attempt + 1}/{self.max_retries})")
                response = self.client.chat.completions.create(**request_params)
                return response
            except Exception as e:
                last_exception = e
                logger.warning(f"DeepSeek API request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        # If we get here, all retries failed
        raise Exception(f"DeepSeek API request failed after {self.max_retries} attempts: {last_exception}")
    
    async def _make_async_request(
        self,
        messages: list,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatCompletion:
        """Async version of _make_request."""
        import asyncio
        
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
        
        # Retry logic
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Making async DeepSeek API request (attempt {attempt + 1}/{self.max_retries})")
                response = await self.async_client.chat.completions.create(**request_params)
                return response
            except Exception as e:
                last_exception = e
                logger.warning(f"Async DeepSeek API request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
        
        raise Exception(f"Async DeepSeek API request failed after {self.max_retries} attempts: {last_exception}")
    
    def extract_specs_from_tz(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Extract technical specifications from raw text or file content.
        
        Args:
            text: Raw text or file content to analyze
            **kwargs: Additional parameters for the API request
            
        Returns:
            Dictionary containing extracted specifications
        """
        system_prompt = self.config.get("prompts", {}).get("extract_specs_from_tz", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Extract technical specifications from the following text:\n\n{text}"
            }
        ]
        
        response = self._make_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        # Parse JSON response
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    async def extract_specs_from_tz_async(self, text: str, **kwargs) -> Dict[str, Any]:
        """Async version of extract_specs_from_tz."""
        import asyncio
        
        system_prompt = self.config.get("prompts", {}).get("extract_specs_from_tz", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Extract technical specifications from the following text:\n\n{text}"
            }
        ]
        
        response = await self._make_async_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    def extract_specs_from_contract_doc(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Extract specifications from parsed PDF/DOCX contract document text.
        
        Args:
            text: Parsed contract document text
            **kwargs: Additional parameters for the API request
            
        Returns:
            Dictionary containing extracted contract specifications
        """
        system_prompt = self.config.get("prompts", {}).get("extract_specs_from_contract_doc", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Extract technical specifications from the following contract document text:\n\n{text}"
            }
        ]
        
        response = self._make_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    async def extract_specs_from_contract_doc_async(self, text: str, **kwargs) -> Dict[str, Any]:
        """Async version of extract_specs_from_contract_doc."""
        import asyncio
        
        system_prompt = self.config.get("prompts", {}).get("extract_specs_from_contract_doc", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Extract technical specifications from the following contract document text:\n\n{text}"
            }
        ]
        
        response = await self._make_async_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    def compare_specs_and_score(
        self,
        target_specs: Dict[str, Any],
        actual_specs: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compare target specifications with actual specifications and calculate match score.
        
        Args:
            target_specs: Target specifications dictionary
            actual_specs: Actual specifications dictionary
            **kwargs: Additional parameters for the API request
            
        Returns:
            Dictionary containing comparison results with score and match type
        """
        system_prompt = self.config.get("prompts", {}).get("compare_specs_and_score", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Compare the following target specifications with actual specifications:\n\n"
                          f"Target Specifications:\n{json.dumps(target_specs, indent=2, ensure_ascii=False)}\n\n"
                          f"Actual Specifications:\n{json.dumps(actual_specs, indent=2, ensure_ascii=False)}\n\n"
                          f"Calculate a match score from 0-100 and determine the match type."
            }
        ]
        
        response = self._make_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    async def compare_specs_and_score_async(
        self,
        target_specs: Dict[str, Any],
        actual_specs: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Async version of compare_specs_and_score."""
        import asyncio
        
        system_prompt = self.config.get("prompts", {}).get("compare_specs_and_score", {}).get("system_prompt", "")
        
        messages = [
            {
                "role": "user",
                "content": f"Compare the following target specifications with actual specifications:\n\n"
                          f"Target Specifications:\n{json.dumps(target_specs, indent=2, ensure_ascii=False)}\n\n"
                          f"Actual Specifications:\n{json.dumps(actual_specs, indent=2, ensure_ascii=False)}\n\n"
                          f"Calculate a match score from 0-100 and determine the match type."
            }
        ]
        
        response = await self._make_async_request(messages, system_prompt, **kwargs)
        content = response.choices[0].message.content
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}\nResponse: {content}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
    
    def generic_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generic completion method for custom prompts.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters for the API request
            
        Returns:
            Response text
        """
        messages = [{"role": "user", "content": prompt}]
        
        response = self._make_request(messages, system_prompt, **kwargs)
        return response.choices[0].message.content
    
    async def generic_completion_async(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Async version of generic_completion."""
        import asyncio
        
        messages = [{"role": "user", "content": prompt}]
        
        response = await self._make_async_request(messages, system_prompt, **kwargs)
        return response.choices[0].message.content


# Singleton instance for easy access
_client_instance: Optional[DeepSeekClient] = None


def get_client() -> DeepSeekClient:
    """Get or create singleton DeepSeekClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = DeepSeekClient()
    return _client_instance


def set_client(client: DeepSeekClient) -> None:
    """Set the singleton DeepSeekClient instance."""
    global _client_instance
    _client_instance = client