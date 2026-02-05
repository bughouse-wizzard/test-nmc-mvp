"""
Tests for DeepSeek AI client.
"""

import json
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from backend.services.ai.client import DeepSeekClient, get_client
from backend.services.ai.prompts import (
    extract_specs_from_tz,
    extract_specs_from_contract_doc,
    compare_specs_and_score,
)


class TestDeepSeekClient:
    """Test DeepSeekClient class."""
    
    def test_client_initialization(self):
        """Test that client can be initialized with default parameters."""
        client = DeepSeekClient(api_key="test-key")
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
        
        client = DeepSeekClient(config_path=str(config_file))
        assert client.api_key == "config-key"
        assert client.base_url == "https://custom.deepseek.com"
        assert client.model == "deepseek-coder"
        assert client.temperature == 0.3
        assert client.max_tokens == 2000
    
    def test_load_config_default(self):
        """Test loading default configuration when no config file exists."""
        client = DeepSeekClient()
        config = client._load_config(None)
        
        assert "deepseek" in config
        assert config["deepseek"]["api_key"] is None
        assert config["deepseek"]["base_url"] == "https://api.deepseek.com"
        assert config["deepseek"]["model"] == "deepseek-chat"
    
    @patch("backend.services.ai.client.OpenAI")
    def test_make_request_success(self, mock_openai_class):
        """Test successful API request."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps({"test": "data"})))]
        
        # Mock client
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        client = DeepSeekClient(api_key="test-key")
        messages = [{"role": "user", "content": "test"}]
        
        response = client._make_request(messages)
        
        assert response == mock_response
        mock_client.chat.completions.create.assert_called_once()
    
    @patch("backend.services.ai.client.OpenAI")
    def test_make_request_retry(self, mock_openai_class):
        """Test API request with retry logic."""
        # Mock client that fails first time, succeeds second time
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = [
            Exception("First failure"),
            Mock(choices=[Mock(message=Mock(content=json.dumps({"test": "data"})))]),
        ]
        mock_openai_class.return_value = mock_client
        
        client = DeepSeekClient(api_key="test-key", max_retries=3)
        messages = [{"role": "user", "content": "test"}]
        
        response = client._make_request(messages)
        
        assert mock_client.chat.completions.create.call_count == 2
        assert response.choices[0].message.content == json.dumps({"test": "data"})
    
    @patch("backend.services.ai.client.DeepSeekClient._make_request")
    def test_extract_specs_from_tz(self, mock_make_request):
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
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(expected_result)))]
        mock_make_request.return_value = mock_response
        
        client = DeepSeekClient(api_key="test-key")
        text = "Test technical documentation"
        
        result = client.extract_specs_from_tz(text)
        
        assert result == expected_result
        mock_make_request.assert_called_once()
    
    @patch("backend.services.ai.client.DeepSeekClient._make_request")
    def test_extract_specs_from_contract_doc(self, mock_make_request):
        """Test extract_specs_from_contract_doc method."""
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
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(expected_result)))]
        mock_make_request.return_value = mock_response
        
        client = DeepSeekClient(api_key="test-key")
        text = "Test contract document"
        
        result = client.extract_specs_from_contract_doc(text)
        
        assert result == expected_result
        mock_make_request.assert_called_once()
    
    @patch("backend.services.ai.client.DeepSeekClient._make_request")
    def test_compare_specs_and_score(self, mock_make_request):
        """Test compare_specs_and_score method."""
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
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content=json.dumps(expected_result)))]
        mock_make_request.return_value = mock_response
        
        client = DeepSeekClient(api_key="test-key")
        target_specs = {"item": "Test", "weight": "10kg"}
        actual_specs = {"item": "Test", "weight": "10kg"}
        
        result = client.compare_specs_and_score(target_specs, actual_specs)
        
        assert result == expected_result
        mock_make_request.assert_called_once()


class TestPromptTemplates:
    """Test prompt templates."""
    
    def test_extract_specs_from_tz_prompt(self):
        """Test extract_specs_from_tz prompt template."""
        prompt = extract_specs_from_tz()
        assert "technical specification extraction expert" in prompt
        assert "JSON format" in prompt
        assert '"items":' in prompt
    
    def test_extract_specs_from_contract_doc_prompt(self):
        """Test extract_specs_from_contract_doc prompt template."""
        prompt = extract_specs_from_contract_doc()
        assert "contract document analysis expert" in prompt
        assert "PDF/DOCX" in prompt
        assert '"contract_items":' in prompt
    
    def test_compare_specs_and_score_prompt(self):
        """Test compare_specs_and_score prompt template."""
        prompt = compare_specs_and_score()
        assert "technical specification comparison expert" in prompt
        assert "match score from 0-100" in prompt
        assert '"score":' in prompt


class TestSingleton:
    """Test singleton pattern."""
    
    def test_get_client_singleton(self):
        """Test that get_client returns singleton instance."""
        client1 = get_client()
        client2 = get_client()
        
        assert client1 is client2
    
    def test_set_client(self):
        """Test that set_client can override singleton instance."""
        from backend.services.ai.client import set_client, _client_instance
        
        original_client = get_client()
        new_client = DeepSeekClient(api_key="new-key")
        
        set_client(new_client)
        
        assert get_client() is new_client
        assert get_client() is not original_client
        
        # Reset for other tests
        set_client(original_client)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])