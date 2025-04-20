import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Import the function to test
from llm_clients.o4_client import query_o4

@pytest.mark.asyncio
async def test_query_o4_success():
    """ Test successful query to O4 wrapper """
    mock_prompt = "Test prompt for O4"
    mock_response = "Successful O4 response"

    # Patch the generate_response method of the llm_o4 instance within the o4_client module
    # Since query_o4 uses asyncio.to_thread, we mock the underlying sync method
    with patch('llm_clients.o4_client.llm_o4.generate_response', return_value=mock_response) as mock_generate:
        response = await query_o4(mock_prompt)

        # Assertions
        assert response == mock_response
        # Check that the underlying sync method was called correctly within the thread
        mock_generate.assert_called_once_with(mock_prompt)

@pytest.mark.asyncio
async def test_query_o4_api_error():
    """ Test query to O4 wrapper when LLMInterface raises an error """
    mock_prompt = "Test prompt causing error"
    mock_exception = Exception("Simulated API Error")

    # Patch generate_response to raise an exception
    with patch('llm_clients.o4_client.llm_o4.generate_response', side_effect=mock_exception) as mock_generate:
        # Expect the exception raised by generate_response to propagate
        with pytest.raises(Exception, match="Simulated API Error"):
            await query_o4(mock_prompt)
        
        mock_generate.assert_called_once_with(mock_prompt)

# Add more tests for different scenarios if needed (e.g., specific error types) 