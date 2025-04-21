# tests/test_debate_engine_v4.py

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

from core.debate_engine_v4 import run_freeform_critique_round
from utils.prompts import FREEFORM_CRITIQUE_PROMPT_TEMPLATE

# --- Test Fixtures --- 

@pytest.fixture
def mock_initial_baselines() -> Dict[str, str]:
    return {
        "O4-mini": "O4 baseline text.",
        "Gemini-2.5": "Gemini baseline text.",
        "Grok-3": "Grok baseline text."
    }

@pytest.fixture
def mock_progress_callback() -> MagicMock:
    return MagicMock()

# --- Test Cases for run_freeform_critique_round --- 

@pytest.mark.asyncio
@patch('core.debate_engine_v4.AGENT_QUERY_FUNCTIONS')
async def test_run_freeform_critique_round_success(mock_query_funcs, mock_initial_baselines, mock_progress_callback):
    """Test successful execution with mock LLM responses."""
    # Arrange
    mock_query_funcs.keys.return_value = list(mock_initial_baselines.keys())
    mock_o4_response = "O4 critique text."
    mock_gemini_response = "Gemini critique text."
    mock_grok_response = "Grok critique text."
    
    # Configure mocks for each agent - IMPORTANT: Use AsyncMock for async functions
    mock_query_funcs.__getitem__.side_effect = lambda key: {
        "O4-mini": AsyncMock(return_value=mock_o4_response),
        "Gemini-2.5": AsyncMock(return_value=mock_gemini_response),
        "Grok-3": AsyncMock(return_value=mock_grok_response)
    }[key]
    
    question = "Test question?"

    # Act
    results = await run_freeform_critique_round(
        initial_baselines=mock_initial_baselines,
        question=question,
        progress_callback=mock_progress_callback
    )

    # Assert
    assert len(results) == 3
    assert results["O4-mini"] == mock_o4_response
    assert results["Gemini-2.5"] == mock_gemini_response
    assert results["Grok-3"] == mock_grok_response

    # Check if query functions were called with correctly formatted prompts
    o4_mock = mock_query_funcs.__getitem__("O4-mini")
    gemini_mock = mock_query_funcs.__getitem__("Gemini-2.5")
    grok_mock = mock_query_funcs.__getitem__("Grok-3")

    o4_mock.assert_called_once()
    gemini_mock.assert_called_once()
    grok_mock.assert_called_once()

    # Verify prompt content for one agent (e.g., O4-mini)
    expected_o4_prompt = FREEFORM_CRITIQUE_PROMPT_TEMPLATE.format(
        question=question,
        your_baseline=mock_initial_baselines["O4-mini"],
        other_baselines_formatted=(
            f"--- Baseline from Agent: Gemini-2.5 ---\n{mock_initial_baselines['Gemini-2.5']}\n--- End Baseline from Agent: Gemini-2.5 ---\n\n"
            f"--- Baseline from Agent: Grok-3 ---\n{mock_initial_baselines['Grok-3']}\n--- End Baseline from Agent: Grok-3 ---"
        )
    )
    o4_mock.assert_called_with(expected_o4_prompt)

    # Check progress callback calls (simplified check)
    mock_progress_callback.assert_any_call("status", "Starting free-form critique round...", use_console=True)
    mock_progress_callback.assert_any_call("agent_status", "Critique received from O4-mini.", use_console=True)
    mock_progress_callback.assert_any_call("freeform_critique_result", {"agent_name": "O4-mini", "critique_text": mock_o4_response}, use_console=False)
    # ... (add similar checks for other agents and status messages)
    mock_progress_callback.assert_any_call("status", "Free-form critique round complete.", use_console=True)


@pytest.mark.asyncio
@patch('core.debate_engine_v4.AGENT_QUERY_FUNCTIONS')
async def test_run_freeform_critique_round_one_agent_fails(mock_query_funcs, mock_initial_baselines, mock_progress_callback):
    """Test when one agent's LLM call raises an exception."""
    # Arrange
    mock_query_funcs.keys.return_value = list(mock_initial_baselines.keys())
    mock_o4_response = "O4 critique text."
    mock_gemini_exception = ValueError("Gemini API Error")
    mock_grok_response = "Grok critique text."

    mock_query_funcs.__getitem__.side_effect = lambda key: {
        "O4-mini": AsyncMock(return_value=mock_o4_response),
        "Gemini-2.5": AsyncMock(side_effect=mock_gemini_exception),
        "Grok-3": AsyncMock(return_value=mock_grok_response)
    }[key]
    
    question = "Test question?"

    # Act
    results = await run_freeform_critique_round(
        initial_baselines=mock_initial_baselines,
        question=question,
        progress_callback=mock_progress_callback
    )

    # Assert
    assert len(results) == 3
    assert results["O4-mini"] == mock_o4_response
    assert results["Gemini-2.5"] == f"Error: {mock_gemini_exception}" # Check error message format
    assert results["Grok-3"] == mock_grok_response

    # Check progress callback for error reporting
    mock_progress_callback.assert_any_call("agent_error", {"agent_name": "Gemini-2.5", "error": f"Error during free-form critique from Gemini-2.5: {mock_gemini_exception}"}, use_console=True)


@pytest.mark.asyncio
@patch('core.debate_engine_v4.AGENT_QUERY_FUNCTIONS')
async def test_run_freeform_critique_round_missing_baseline(mock_query_funcs, mock_initial_baselines, mock_progress_callback):
    """Test when one agent is missing an initial baseline."""
    # Arrange
    del mock_initial_baselines["Grok-3"] # Simulate Grok failing baseline gen
    mock_query_funcs.keys.return_value = ["O4-mini", "Gemini-2.5", "Grok-3"] # Engine still knows about Grok
    
    mock_o4_response = "O4 critique text."
    mock_gemini_response = "Gemini critique text."

    # Only O4 and Gemini should be called
    mock_query_funcs.__getitem__.side_effect = lambda key: {
        "O4-mini": AsyncMock(return_value=mock_o4_response),
        "Gemini-2.5": AsyncMock(return_value=mock_gemini_response),
        # Grok mock shouldn't be called
    }[key]
    
    question = "Test question?"

    # Act
    results = await run_freeform_critique_round(
        initial_baselines=mock_initial_baselines,
        question=question,
        progress_callback=mock_progress_callback
    )

    # Assert
    assert len(results) == 2 # Only O4 and Gemini should have results
    assert results["O4-mini"] == mock_o4_response
    assert results["Gemini-2.5"] == mock_gemini_response
    assert "Grok-3" not in results

    # Verify Grok's query function was never called
    with pytest.raises(KeyError): # Accessing a mock that wasn't configured raises error
         mock_query_funcs.__getitem__("Grok-3")
    # Or more directly if needed:
    # assert not mock_query_funcs.__getitem__("Grok-3").called

    # Check status messages
    mock_progress_callback.assert_any_call("status", f"Querying 2 agents for free-form critique...", use_console=False) 