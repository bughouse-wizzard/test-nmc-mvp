"""
Tests for LLMClient (DeepSeek integration service).
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from app.services.ai.llm_client import LLMClient, get_llm_client, set_llm_client


class TestLLMClient:
    """Test LLMClient class."""
    
    def test_client_initialization(self):
        """Test that client can be initialized with default parameters."""
        client = LLMClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.base_url == "https://api.deepseek.com"
        assert client.model == "deepseek-chat"
        assert client.temperature == 0.1
        assert client.max_tokens == 4000
    
    def test_client_initialization_with_config(self, tmp_path):
        """Test that client loads configuration from YAML file."""
        config_content = """
deepseek:
  api_key: "config-key"
  base_url: "https://custom.deepseek.com"
  model: "deepseek-coder"
  temperature: 0.3
  max_tokens: 2000
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)
        
        client = LLMClient(config_path=str(config_file))
        assert client.api_key == "config-key"
        assert client.base_url == "https://custom.deepseek.com"
        assert client.model == "deepseek-coder"
        assert client.temperature == 0.3
        assert client.max_tokens == 2000
    
    @patch("app.services.ai.llm_client.Path")
    def test_load_config_default(self, mock_path):
        """Test loading default configuration when no config file exists."""
        # Mock Path to simulate non-existent config file
        mock_path_instance = mock_path.return_value
        mock_path_instance.exists.return_value = False
        
        client = LLMClient(api_key="test-key")
        # Pass a non-existent config path
        config = client._load_config("/non/existent/path/config.yaml")
        
        assert "deepseek" in config
        # When loading from non-existent path and default config.yaml doesn't exist,
        # should return the hardcoded default config
        assert config["deepseek"]["api_key"] is None
        assert config["deepseek"]["base_url"] == "https://api.deepseek.com"
        assert config["deepseek"]["model"] == "deepseek-chat"
    
    @patch("app.services.ai.llm_client.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_make_request_success(self, mock_openai_class):
        """Test successful API request."""
        # Mock response
        mock_response = AsyncMock()
        mock_response.id = "test-id"
        mock_response.model = "deepseek-chat"
        mock_response.created = 1234567890
        mock_response.usage = Mock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        mock_response.choices = [Mock(message=Mock(content=json.dumps({"test": "data"})))]
        
        # Mock async client
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client
        
        client = LLMClient(api_key="test-key")
        messages = [{"role": "user", "content": "test"}]
        
        response = await client._make_request(messages)
        
        assert response == mock_response
        mock_client.chat.completions.create.assert_called_once()
    
    @patch("app.services.ai.llm_client.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_make_request_retry(self, mock_openai_class):
        """Test API request with retry logic."""
        # Mock client that fails first time, succeeds second time
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[
            Exception("First failure"),
            Mock(
                id="test-id",
                model="deepseek-chat",
                created=1234567890,
                usage=Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150),
                choices=[Mock(message=Mock(content=json.dumps({"test": "data"})))]
            ),
        ])
        mock_openai_class.return_value = mock_client
        
        # Create client with config that has max_retries
        client = LLMClient(api_key="test-key")
        # Manually set max_retries for testing
        client.max_retries = 3
        messages = [{"role": "user", "content": "test"}]
        
        response = await client._make_request(messages)
        
        assert mock_client.chat.completions.create.call_count == 2
        assert response.choices[0].message.content == json.dumps({"test": "data"})
    
    def test_extract_json_from_text(self):
        """Test JSON extraction from text."""
        client = LLMClient(api_key="test-key")
        
        # Test with JSON code block
        text_with_codeblock = "Here is the JSON:\n```json\n{\"test\": \"data\"}\n```"
        result = client._extract_json_from_text(text_with_codeblock)
        assert result == '{"test": "data"}'
        
        # Test with generic code block
        text_with_generic = "Here is the JSON:\n```\n{\"test\": \"data\"}\n```"
        result = client._extract_json_from_text(text_with_generic)
        assert result == '{"test": "data"}'
        
        # Test with plain JSON object
        text_plain = '{"test": "data"}'
        result = client._extract_json_from_text(text_plain)
        assert result == '{"test": "data"}'
        
        # Test with JSON array
        text_array = '[{"item": "one"}, {"item": "two"}]'
        result = client._extract_json_from_text(text_array)
        assert result == '[{"item": "one"}, {"item": "two"}]'
        
        # Test with JSON array in text
        text_array_in_text = "Some text before\n[{\"item\": \"one\"}, {\"item\": \"two\"}]\nSome text after"
        result = client._extract_json_from_text(text_array_in_text)
        assert result == '[{"item": "one"}, {"item": "two"}]'
    
    def test_repair_json(self):
        """Test JSON repair functionality."""
        client = LLMClient(api_key="test-key")
        
        # Test valid JSON (should not change)
        valid_json = '{"test": "data"}'
        result = client._repair_json(valid_json)
        assert result == valid_json
        
        # Test JSON with trailing comma
        json_with_trailing_comma = '{"test": "data",}'
        result = client._repair_json(json_with_trailing_comma)
        assert result == '{"test": "data"}'
        
        # Test JSON with single quotes
        json_single_quotes = "{'test': 'data'}"
        result = client._repair_json(json_single_quotes)
        assert result == '{"test": "data"}'
        
        # Test JSON without quotes on keys
        json_no_quotes = '{test: "data"}'
        result = client._repair_json(json_no_quotes)
        assert result == '{"test": "data"}'
        
        # Test JSON with escaped single quotes
        json_escaped_single = '{"test": "don\'t worry"}'
        result = client._repair_json(json_escaped_single)
        # Should preserve the escaped single quote
        assert "don't" in result
    
    @patch("app.services.ai.llm_client.LLMClient._make_request")
    @pytest.mark.asyncio
    async def test_extract_specs_from_tz(self, mock_make_request):
        """Test extract_specs_from_tz method."""
        # Mock response
        expected_result = {
            "items": [
                {
                    "name": "Test Product",
                    "parameters": [
                        {"name": "Weight", "value": "10", "unit": "kg"}
                    ],
                    "quantity": "100",
                    "quality_standards": ["ISO 9001"],
                    "delivery_requirements": "Within 30 days",
                    "notes": "Test notes"
                }
            ]
        }
        
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(expected_result)))]
        mock_response.debug_data = {"test": "debug"}
        mock_make_request.return_value = mock_response
        
        client = LLMClient(api_key="test-key")
        text = "Test technical documentation"
        
        result = await client.extract_specs_from_tz(text)
        
        # Check that expected_result is contained in result (result has _debug added)
        for key, value in expected_result.items():
            assert key in result
            assert result[key] == value
        assert "_debug" in result
        mock_make_request.assert_called_once()
    
    @patch("app.services.ai.llm_client.LLMClient._make_request")
    @pytest.mark.asyncio
    async def test_extract_specs_from_contract(self, mock_make_request):
        """Test extract_specs_from_contract method."""
        # Mock response
        expected_result = {
            "contract_items": [
                {
                    "item_name": "Test Item",
                    "description": "Test description",
                    "technical_specs": [
                        {"parameter": "Size", "requirement": "10x20", "unit": "cm"}
                    ],
                    "quantity": "50",
                    "unit_of_measurement": "pieces",
                    "quality_requirements": ["Grade A"],
                    "delivery_schedule": "Q1 2024",
                    "price": "1000",
                    "currency": "USD",
                    "contract_conditions": ["FOB"]
                }
            ]
        }
        
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(expected_result)))]
        mock_response.debug_data = {"test": "debug"}
        mock_make_request.return_value = mock_response
        
        client = LLMClient(api_key="test-key")
        text = "Test contract document"
        
        result = await client.extract_specs_from_contract(text)
        
        # Check that expected_result is contained in result (result has _debug added)
        for key, value in expected_result.items():
            assert key in result
            assert result[key] == value
        assert "_debug" in result
        mock_make_request.assert_called_once()
    
    @patch("app.services.ai.llm_client.LLMClient._make_request")
    @pytest.mark.asyncio
    async def test_compare_specs(self, mock_make_request):
        """Test compare_specs method."""
        # Mock response
        expected_result = {
            "score": 85,
            "match_type": "Homogeneous",
            "details": {
                "parameter_matches": [
                    {
                        "parameter": "Weight",
                        "target_value": "10",
                        "actual_value": "10",
                        "match": True,
                        "notes": "Exact match"
                    }
                ],
                "quantity_match": True,
                "quality_standards_match": True,
                "delivery_match": True
            },
            "summary": "Good match with minor differences"
        }
        
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(expected_result)))]
        mock_response.debug_data = {"test": "debug"}
        mock_make_request.return_value = mock_response
        
        client = LLMClient(api_key="test-key")
        target_specs = {"item": "Test", "weight": "10kg"}
        contract_specs = {"item": "Test", "weight": "10kg"}
        
        result = await client.compare_specs(target_specs, contract_specs)
        
        # Check that expected_result is contained in result (result has _debug added)
        for key, value in expected_result.items():
            assert key in result
            assert result[key] == value
        assert "_debug" in result
        mock_make_request.assert_called_once()
    
    @patch("app.services.ai.llm_client.LLMClient._make_request")
    @pytest.mark.asyncio
    async def test_extract_specs_from_tz_with_json_repair(self, mock_make_request):
        """Test extract_specs_from_tz with JSON that needs repair."""
        # Mock response with malformed JSON (single quotes instead of double)
        # The repair function should handle this
        raw_response = "Here's the JSON:\n```json\n{'items': [{'name': 'Test', 'parameters': []}]}\n```"
        expected_result = {
            "items": [
                {
                    "name": "Test",
                    "parameters": []
                }
            ]
        }
        
        mock_response = AsyncMock()
        mock_response.choices = [Mock(message=Mock(content=raw_response))]
        mock_response.debug_data = {"test": "debug"}
        mock_make_request.return_value = mock_response
        
        client = LLMClient(api_key="test-key")
        text = "Test technical documentation"
        
        result = await client.extract_specs_from_tz(text)
        
        # Check that expected_result is contained in result (result has _debug added)
        for key, value in expected_result.items():
            assert key in result
            assert result[key] == value
        assert "_debug" in result
        mock_make_request.assert_called_once()


class TestSingleton:
    """Test singleton pattern."""
    
    @pytest.mark.asyncio
    async def test_get_llm_client_singleton(self):
        """Test that get_llm_client returns singleton instance."""
        client1 = await get_llm_client()
        client2 = await get_llm_client()
        
        assert client1 is client2
    
    @pytest.mark.asyncio
    async def test_set_llm_client(self):
        """Test that set_llm_client can override singleton instance."""
        original_client = await get_llm_client()
        new_client = LLMClient(api_key="new-key")
        
        set_llm_client(new_client)
        
        assert await get_llm_client() is new_client
        assert await get_llm_client() is not original_client
        
        # Reset for other tests
        set_llm_client(original_client)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])