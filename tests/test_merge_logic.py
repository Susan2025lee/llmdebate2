import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock, call
import json # Add json import

from utils.models import Factor, AgentResponse
# Adjust path if merge_factors was moved or needs different imports
from core.merge_logic import merge_factors # Assuming merge_factors is still here
from llm_interface import LLMInterface # For patching
from utils.prompts import MERGE_FACTORS_PROMPT # For checking prompt format

# --- Test Data Setup --- 

# Basic factors
F_A = Factor(name="A", justification="Justification A", confidence=4)
F_B = Factor(name="B", justification="Justification B", confidence=5)
F_C = Factor(name="C", justification="Justification C", confidence=3)
F_D = Factor(name="D", justification="Justification D", confidence=5)

# Agent responses for testing
RESP_1 = AgentResponse(agent_name="Agent1", factors=[F_A, F_B, F_D])
RESP_2 = AgentResponse(agent_name="Agent2", factors=[F_A, F_C])

FINAL_RESPONSES_BASIC = {"Agent1": RESP_1, "Agent2": RESP_2}

# --- Test Cases --- 

# Use pytest.mark.asyncio for async functions
@pytest.mark.asyncio
@patch('core.merge_logic.LLMInterface') # Patch LLMInterface where it's used
async def test_merge_llm_basic(MockLLMInterface):
    """ Test LLM-based merge logic with a successful mock response. """
    # Arrange
    mock_question = "Test question for merge?"
    mock_top_k = 3
    # Mock the LLM response JSON string
    mock_llm_json_output = json.dumps([
        {"name": "Synthesized A", "justification": "Merged Justification A", "confidence": 4.5},
        {"name": "Synthesized B", "justification": "Merged Justification B", "confidence": 5.0},
        {"name": "Synthesized D", "justification": "Merged Justification D", "confidence": 5.0}
    ])
    mock_llm_instance = MagicMock(spec=LLMInterface)
    mock_llm_instance.generate_response.return_value = mock_llm_json_output
    MockLLMInterface.return_value = mock_llm_instance

    # Act
    merged = await merge_factors(
        final_responses=FINAL_RESPONSES_BASIC,
        question=mock_question,
        top_k=mock_top_k
    )

    # Assert
    assert len(merged) == 3
    assert merged[0].name == "Synthesized A"
    assert merged[0].confidence == 4.5
    assert merged[1].name == "Synthesized B"
    assert merged[2].name == "Synthesized D"

    # Check that LLMInterface was initialized and called
    MockLLMInterface.assert_called_once()
    mock_llm_instance.generate_response.assert_called_once()
    
    # Optionally check the prompt format
    call_args, _ = mock_llm_instance.generate_response.call_args
    prompt_arg = call_args[0]
    assert mock_question in prompt_arg
    assert f"top {mock_top_k}" in prompt_arg
    assert "Factors from Agent1:" in prompt_arg
    assert "Factors from Agent2:" in prompt_arg
    assert F_A.name in prompt_arg
    assert F_C.name in prompt_arg

@pytest.mark.asyncio
@patch('core.merge_logic.LLMInterface')
async def test_merge_llm_top_k_trimming(MockLLMInterface):
    """ Test that merge_factors trims results if LLM returns more than top_k. """
    # Arrange
    mock_question = "Test question for merge?"
    mock_top_k = 2 # Ask for top 2
    # Mock LLM returning 3 factors
    mock_llm_json_output = json.dumps([
        {"name": "Factor 1", "justification": "J1", "confidence": 5.0},
        {"name": "Factor 2", "justification": "J2", "confidence": 4.0},
        {"name": "Factor 3", "justification": "J3", "confidence": 3.0}
    ])
    mock_llm_instance = MagicMock(spec=LLMInterface)
    mock_llm_instance.generate_response.return_value = mock_llm_json_output
    MockLLMInterface.return_value = mock_llm_instance

    # Act
    merged = await merge_factors(
        final_responses=FINAL_RESPONSES_BASIC,
        question=mock_question,
        top_k=mock_top_k
    )

    # Assert
    assert len(merged) == mock_top_k # Should be trimmed to 2
    assert merged[0].name == "Factor 1"
    assert merged[1].name == "Factor 2"

@pytest.mark.asyncio
@patch('core.merge_logic.LLMInterface')
async def test_merge_llm_json_parse_error(MockLLMInterface):
    """ Test handling of invalid JSON from the LLM. """
    # Arrange
    mock_question = "Test question for merge?"
    mock_llm_bad_json = 'This is not JSON [{"name": "Bad"}]'
    mock_llm_instance = MagicMock(spec=LLMInterface)
    mock_llm_instance.generate_response.return_value = mock_llm_bad_json
    MockLLMInterface.return_value = mock_llm_instance

    # Act
    merged = await merge_factors(
        final_responses=FINAL_RESPONSES_BASIC,
        question=mock_question,
        top_k=5
    )

    # Assert
    assert merged == [] # Should return empty list on parse error

@pytest.mark.asyncio
@patch('core.merge_logic.LLMInterface')
async def test_merge_llm_api_error(MockLLMInterface):
    """ Test handling of an exception during the LLM API call. """
    # Arrange
    mock_question = "Test question for merge?"
    mock_llm_instance = MagicMock(spec=LLMInterface)
    mock_llm_instance.generate_response.side_effect = Exception("API Failure")
    MockLLMInterface.return_value = mock_llm_instance

    # Act
    merged = await merge_factors(
        final_responses=FINAL_RESPONSES_BASIC,
        question=mock_question,
        top_k=5
    )

    # Assert
    assert merged == [] # Should return empty list on API error

@pytest.mark.asyncio
@patch('core.merge_logic.LLMInterface')
async def test_merge_no_input_factors(MockLLMInterface):
    """ Test merging when the input responses contain no factors. """
    # Arrange
    mock_question = "Test question for merge?"
    resp_empty1 = AgentResponse(agent_name="Empty1", factors=[])
    resp_empty2 = AgentResponse(agent_name="Empty2", factors=[])
    empty_responses = {"E1": resp_empty1, "E2": resp_empty2}
    mock_llm_instance = MagicMock(spec=LLMInterface) # Mock instance needed for patch
    MockLLMInterface.return_value = mock_llm_instance

    # Act
    merged = await merge_factors(
        final_responses=empty_responses,
        question=mock_question,
        top_k=5
    )

    # Assert
    assert merged == [] # Should return empty list
    # Crucially, the LLM should NOT have been called
    mock_llm_instance.generate_response.assert_not_called()

# Remove old algorithmic tests or adapt them significantly if needed.
# The following tests are removed as they tested the old non-LLM logic:
# - test_merge_basic_endorsement_and_confidence
# - test_merge_top_k_filtering (replaced with LLM version)
# - test_merge_stricter_thresholds 
# - test_merge_case_insensitivity_and_whitespace
# - test_merge_no_responses
# - test_merge_empty_factors (replaced with LLM version)
# - test_merge_no_consensus