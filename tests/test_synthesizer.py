# tests/test_synthesizer.py

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock, call
from typing import Dict, Any, List, Optional, Callable

# Make sure the path allows importing from core and utils
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from core.synthesizer import synthesize_final_answer, _format_dict_for_prompt, _format_debate_rounds_for_prompt
from utils.prompts import SYNTHESIS_PROMPT_TEMPLATE
from llm_interface import LLMInterface # Need this for patching

# --- Test Fixtures --- 

@pytest.fixture
def mock_baselines() -> Dict[str, str]:
    return {
        "Agent1": "Baseline from Agent1.",
        "Agent2": "Baseline from Agent2."
    }

@pytest.fixture
def mock_debate_rounds() -> List[Dict[str, Any]]:
    return [
        {
            "round": 1,
            "responses": {
                "Agent1": "Critique round 1 text from Agent1.",
                "Agent2": "Critique round 1 text from Agent2."
            }
        }
        # Add more rounds if testing multi-round scenarios later
    ]

@pytest.fixture
def mock_progress_callback() -> MagicMock:
    return MagicMock()

# --- Test Helper Functions --- 

def test_format_dict_for_prompt():
    data = {"Agent1": "Text1", "Agent2": "Text2"}
    expected = (
        "--- TestPrefix from Agent: Agent1 ---\nText1\n--- End TestPrefix from Agent: Agent1 ---\n\n"
        "--- TestPrefix from Agent: Agent2 ---\nText2\n--- End TestPrefix from Agent: Agent2 ---"
    )
    assert _format_dict_for_prompt(data, "TestPrefix") == expected

def test_format_debate_rounds_for_prompt(mock_debate_rounds):
    expected = (
        "=== Debate Round 1 ===\n\n"
        "--- Response from Agent: Agent1 ---\nCritique round 1 text from Agent1.\n--- End Response from Agent: Agent1 ---\n\n"
        "--- Response from Agent: Agent2 ---\nCritique round 1 text from Agent2.\n--- End Response from Agent: Agent2 ---"
        # Add expected output for more rounds if fixture changes
    )
    assert _format_debate_rounds_for_prompt(mock_debate_rounds) == expected

# --- Test Cases for synthesize_final_answer --- 

@pytest.mark.asyncio
@patch('core.synthesizer.LLMInterface') # Patch the LLMInterface class
async def test_synthesize_final_answer_success(MockLLMInterface, mock_baselines, mock_debate_rounds, mock_progress_callback):
    """Test successful synthesis with a mock LLM response."""
    # Arrange
    mock_synthesizer_response = "This is the synthesized final answer."
    mock_llm_instance = MagicMock(spec=LLMInterface)
    # Mock the async behavior properly for generate_response called via to_thread
    mock_llm_instance.generate_response = MagicMock(return_value=mock_synthesizer_response)
    mock_llm_instance.close = MagicMock()
    mock_llm_instance.model_name = "mock-model"
    MockLLMInterface.return_value = mock_llm_instance
    
    question = "Synthesize this?"

    # Act
    result = await synthesize_final_answer(
        question=question,
        initial_baselines=mock_baselines,
        debate_rounds=mock_debate_rounds,
        progress_callback=mock_progress_callback
    )

    # Assert
    assert result == mock_synthesizer_response
    
    # Check LLMInterface initialization
    MockLLMInterface.assert_called_once_with(model_key="gpt-o4-mini")

    # Check prompt formatting
    baselines_formatted = _format_dict_for_prompt(mock_baselines, "Baseline")
    critiques_formatted = _format_debate_rounds_for_prompt(mock_debate_rounds)
    expected_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        question=question,
        initial_baselines_formatted=baselines_formatted,
        critique_texts_formatted=critiques_formatted
    )
    
    # Verify generate_response call arguments
    mock_llm_instance.generate_response.assert_called_once_with(
        prompt=expected_prompt,
        temperature=0.5
    )
    
    mock_llm_instance.close.assert_called_once()

    # Check progress callback calls (simplified)
    mock_progress_callback.assert_any_call("status", "Starting final answer synthesis...", use_console=True)
    mock_progress_callback.assert_any_call("status", "Querying synthesizer model (mock-model)...", use_console=False)
    mock_progress_callback.assert_any_call("status", "Synthesis complete.", use_console=True)


@pytest.mark.asyncio
@patch('core.synthesizer.LLMInterface')
async def test_synthesize_final_answer_llm_init_fails(MockLLMInterface, mock_baselines, mock_debate_rounds, mock_progress_callback):
    """Test when LLMInterface initialization fails."""
    # Arrange
    init_exception = ValueError("Invalid API Key")
    MockLLMInterface.side_effect = init_exception
    
    question = "Synthesize this?"

    # Act
    result = await synthesize_final_answer(
        question=question,
        initial_baselines=mock_baselines,
        debate_rounds=mock_debate_rounds,
        progress_callback=mock_progress_callback
    )

    # Assert
    expected_error = f"Error: Could not initialize synthesizer model. {init_exception}"
    assert result == expected_error
    MockLLMInterface.assert_called_once_with(model_key="gpt-o4-mini")
    mock_progress_callback.assert_any_call("error", f"Error initializing synthesizer LLM (gpt-o4-mini): {init_exception}", use_console=True)

@pytest.mark.asyncio
@patch('core.synthesizer.LLMInterface')
async def test_synthesize_final_answer_llm_call_fails(MockLLMInterface, mock_baselines, mock_debate_rounds, mock_progress_callback):
    """Test when the generate_response call fails."""
     # Arrange
    call_exception = Exception("API Timeout")
    mock_llm_instance = MagicMock(spec=LLMInterface)
    # Mock the async behavior properly for generate_response called via to_thread
    mock_llm_instance.generate_response = MagicMock(side_effect=call_exception)
    mock_llm_instance.close = MagicMock()
    mock_llm_instance.model_name = "mock-model"
    MockLLMInterface.return_value = mock_llm_instance
    
    question = "Synthesize this?"

    # Act
    result = await synthesize_final_answer(
        question=question,
        initial_baselines=mock_baselines,
        debate_rounds=mock_debate_rounds,
        progress_callback=mock_progress_callback
    )

    # Assert
    expected_error = f"Error: Synthesis failed due to LLM error: {call_exception}"
    assert result == expected_error
    mock_progress_callback.assert_any_call("error", f"Error during synthesis call: {call_exception}", use_console=True)
    mock_llm_instance.close.assert_called_once() # Close should still be called 