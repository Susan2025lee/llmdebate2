import pytest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock, call

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Modules to test
from core.summarizer import generate_summary
from utils.models import Factor
from utils.prompts import SUMMARIZATION_PROMPT_TEMPLATE # To check formatting

# --- Test Data --- 

MERGED_FACTOR_A = Factor(name="A", justification="(Agent1): JA1\n(Agent2): JA2", confidence=4.5)
setattr(MERGED_FACTOR_A, 'endorsement_count', 2)

MERGED_FACTOR_B = Factor(name="B", justification="(Agent1): JB1\n(Agent2): JB2", confidence=4.0)
setattr(MERGED_FACTOR_B, 'endorsement_count', 2)

MERGED_FACTORS_BASIC = [MERGED_FACTOR_A, MERGED_FACTOR_B]

# --- Test Cases --- 

@pytest.mark.asyncio
@patch('core.summarizer.query_o4', new_callable=AsyncMock) # Mock the LLM call
@patch('core.summarizer.typer.secho') # Mock printing
async def test_generate_summary_success(mock_secho, mock_query_o4):
    """ Test successful summary generation and prompt formatting. """
    mock_llm_summary = "This is the final summary based on factors A and B."
    mock_query_o4.return_value = mock_llm_summary
    
    summary = await generate_summary(MERGED_FACTORS_BASIC)
    
    assert summary == mock_llm_summary
    mock_secho.assert_any_call("\nGenerating final summary...", fg='yellow')
    
    # Verify prompt formatting
    mock_query_o4.assert_awaited_once() 
    call_args, call_kwargs = mock_query_o4.call_args
    generated_prompt = call_args[0]
    
    # Reconstruct expected prompt parts
    expected_consensus_details = (
        f"1. A (Endorsements: 2, Mean Confidence: 4.50)\n"
        f"2. B (Endorsements: 2, Mean Confidence: 4.00)"
    )
    expected_justifications = (
        f"Factor: A\n(Agent1): JA1\n(Agent2): JA2\n\n"
        f"Factor: B\n(Agent1): JB1\n(Agent2): JB2\n"
    )
    expected_full_prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(
        consensus_factors_details=expected_consensus_details,
        all_justifications=expected_justifications
    )
    
    assert generated_prompt == expected_full_prompt

@pytest.mark.asyncio
async def test_generate_summary_no_factors():
    """ Test summary generation when the input factor list is empty. """
    summary = await generate_summary([])
    assert summary == "No consensus factors were identified to generate a summary."

@pytest.mark.asyncio
@patch('core.summarizer.query_o4', new_callable=AsyncMock) # Mock the LLM call
@patch('core.summarizer.typer.secho') # Mock printing
async def test_generate_summary_llm_error(mock_secho, mock_query_o4):
    """ Test summary generation when the LLM call raises an error. """
    mock_exception = Exception("Simulated LLM Error during summary")
    mock_query_o4.side_effect = mock_exception
    
    summary = await generate_summary(MERGED_FACTORS_BASIC)
    
    assert "Error: Failed to generate summary" in summary
    assert "Simulated LLM Error during summary" in summary
    mock_query_o4.assert_awaited_once() # Ensure it was called
    mock_secho.assert_any_call("\nGenerating final summary...", fg='yellow') 