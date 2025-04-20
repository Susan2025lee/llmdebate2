import pytest
import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock, ANY
import unittest

# Import the function to test
from llm_clients.gemini_client import query_gemini

# Mock response object structure expected from google.generativeai
class MockGeminiResponse:
    def __init__(self, text):
        self.text = text

@pytest.mark.asyncio
async def test_query_gemini_success():
    """ Test successful query to Gemini wrapper with direct API call """
    mock_prompt = "Test prompt for Gemini"
    mock_response_text = "Successful Gemini response"
    mock_response_obj = MockGeminiResponse(text=mock_response_text)

    # Patch the generate_content method of the genai_model instance
    # Since query_gemini uses asyncio.to_thread, we mock the underlying sync method
    with patch('llm_clients.gemini_client.genai_model.generate_content', return_value=mock_response_obj) as mock_generate:
        response = await query_gemini(mock_prompt)

        # Assertions
        assert response == mock_response_text
        mock_generate.assert_called_once()
        # We can add more specific checks on args/kwargs if needed
        # Example: checking the prompt and generation_config structure
        args, kwargs = mock_generate.call_args
        assert args[0] == mock_prompt
        assert 'generation_config' in kwargs
        assert kwargs['generation_config'].temperature == 0.7 # Default temperature

@pytest.mark.asyncio
async def test_query_gemini_no_api_key():
    """ Test Gemini wrapper when API key is missing (genai_model is None) """
    mock_prompt = "Test prompt, no API key"

    # Patch the genai_model to simulate it being None
    with patch('llm_clients.gemini_client.genai_model', None):
        response = await query_gemini(mock_prompt)

        # Assertions
        assert "Error: Gemini client not configured" in response

@pytest.mark.asyncio
async def test_query_gemini_api_error():
    """ Test Gemini wrapper when generate_content raises an error """
    mock_prompt = "Test prompt causing Gemini error"
    mock_exception = Exception("Simulated Gemini API Error")

    # Patch generate_content to raise an exception
    with patch('llm_clients.gemini_client.genai_model.generate_content', side_effect=mock_exception) as mock_generate:
        response = await query_gemini(mock_prompt)
        
        # Assertions
        assert "Error: Failed to get response from Gemini" in response
        assert "Simulated Gemini API Error" in response
        mock_generate.assert_called_once_with(mock_prompt, generation_config=unittest.mock.ANY)

@pytest.mark.asyncio
async def test_query_gemini_bad_response_format():
    """ Test Gemini wrapper when the response object lacks the .text attribute """
    mock_prompt = "Test prompt for bad response"
    # Create a mock object that doesn't have a .text attribute
    mock_bad_response_obj = MagicMock(spec=[]) 

    with patch('llm_clients.gemini_client.genai_model.generate_content', return_value=mock_bad_response_obj) as mock_generate:
        response = await query_gemini(mock_prompt)

        # Assertions
        assert "Error: Received unexpected response from Gemini" in response
        mock_generate.assert_called_once()

# Test with custom temperature/max_tokens (optional)
@pytest.mark.asyncio
async def test_query_gemini_custom_config():
    """ Test successful query to Gemini wrapper with custom config """
    mock_prompt = "Test prompt for Gemini custom config"
    mock_response_text = "Successful Gemini response with custom config"
    mock_response_obj = MockGeminiResponse(text=mock_response_text)
    custom_temp = 0.9
    custom_max_tokens = 100

    with patch('llm_clients.gemini_client.genai_model.generate_content', return_value=mock_response_obj) as mock_generate:
        response = await query_gemini(mock_prompt, temperature=custom_temp, max_tokens=custom_max_tokens)

        # Assertions
        assert response == mock_response_text
        mock_generate.assert_called_once()
        args, kwargs = mock_generate.call_args
        assert kwargs['generation_config'].temperature == custom_temp
        # Check max_tokens if API supports it, otherwise ignore 