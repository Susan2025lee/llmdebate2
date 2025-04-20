import pytest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock, call
import typer # Used for type hints and potentially mocking

# Add project root to sys.path to allow importing 'debate'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the async function to test
from debate import run_debate_logic

# Since run_debate_logic imports clients inside, we patch them there
@pytest.mark.asyncio
@patch('llm_clients.o4_client.query_o4', new_callable=AsyncMock)
@patch('llm_clients.gemini_client.query_gemini', new_callable=AsyncMock)
@patch('debate.typer.secho') # Mock typer output
@patch('debate.typer.echo')  # Mock typer output
async def test_run_baseline_success(mock_echo, mock_secho, mock_query_gemini, mock_query_o4):
    """ Test the baseline fan-out logic successfully queries O4 and Gemini """
    # Mock return values for the client queries
    mock_o4_response = "O4 Factors: A, B, C"
    mock_gemini_response = "Gemini Factors: A, D, E"
    mock_query_o4.return_value = mock_o4_response
    mock_query_gemini.return_value = mock_gemini_response

    test_question = "Test question?"
    test_top_k = 3

    # Run the logic
    await run_debate_logic(
        question=test_question, 
        top_k=test_top_k, 
        max_rounds=3, 
        output="test.json", 
        verbose=False
    )

    # --- Assertions --- #
    # 1. Check prompt construction (implicitly checked by calls below)
    expected_prompt = (
        f"Q: {test_question}\n"
        f"List top {test_top_k} factors with 1–2 sentence justification and self-rated confidence (1–5)."
    )

    # 2. Check that client queries were called correctly
    mock_query_o4.assert_awaited_once_with(expected_prompt)
    mock_query_gemini.assert_awaited_once_with(expected_prompt)

    # 3. Check that typer.secho was called to print results
    # Note: Call order might vary slightly due to asyncio.gather, focus on content
    # print(f"secho calls: {mock_secho.call_args_list}") # Debug print
    secho_calls = mock_secho.call_args_list
    assert call("\nQuerying baseline models...", fg=typer.colors.YELLOW) in secho_calls
    assert call("\n[Baseline Results]", fg=typer.colors.YELLOW) in secho_calls
    assert call(f"[O4-mini] {mock_o4_response}", fg=typer.colors.BLUE) in secho_calls
    assert call(f"[Gemini-2.5] {mock_gemini_response}", fg=typer.colors.BLUE) in secho_calls

    # 4. Check that the TODO echo was called
    mock_echo.assert_any_call("\n[TODO] Implement Debate Rounds, Merge, Summarize, Judge...")

@pytest.mark.asyncio
@patch('llm_clients.o4_client.query_o4', new_callable=AsyncMock)
@patch('llm_clients.gemini_client.query_gemini', new_callable=AsyncMock)
@patch('debate.typer.secho') # Mock typer output
@patch('debate.typer.echo')  # Mock typer output
async def test_run_baseline_one_client_fails(mock_echo, mock_secho, mock_query_gemini, mock_query_o4):
    """ Test baseline fan-out when one client query raises an exception """
    mock_o4_response = "O4 Factors: A, B, C"
    mock_gemini_exception = ValueError("Gemini API Error")
    mock_query_o4.return_value = mock_o4_response
    mock_query_gemini.side_effect = mock_gemini_exception

    test_question = "Test question where Gemini fails?"
    test_top_k = 5

    # Run the logic (should not raise an error due to return_exceptions=True)
    await run_debate_logic(
        question=test_question, 
        top_k=test_top_k, 
        max_rounds=3, 
        output="test.json", 
        verbose=False
    )

    # --- Assertions --- #
    expected_prompt = (
        f"Q: {test_question}\n"
        f"List top {test_top_k} factors with 1–2 sentence justification and self-rated confidence (1–5)."
    )
    mock_query_o4.assert_awaited_once_with(expected_prompt)
    mock_query_gemini.assert_awaited_once_with(expected_prompt)

    # Check that typer.secho prints the success and the error
    secho_calls = mock_secho.call_args_list
    assert call(f"[O4-mini] {mock_o4_response}", fg=typer.colors.BLUE) in secho_calls
    assert call(f"[Gemini-2.5] Error: {mock_gemini_exception}", fg=typer.colors.RED) in secho_calls
    
    # Check that the TODO echo was still called
    mock_echo.assert_any_call("\n[TODO] Implement Debate Rounds, Merge, Summarize, Judge...")

# Potential future test: Mocking the Grok import successfully
# @pytest.mark.asyncio
# @patch('debate.query_o4', new_callable=AsyncMock)
# @patch('debate.query_gemini', new_callable=AsyncMock)
# @patch('debate.query_grok', new_callable=AsyncMock) # Mock grok as well
# @patch('debate.typer.secho')
# @patch('debate.typer.echo')
# async def test_run_baseline_with_grok(...):
#     # ... setup mocks for all 3 clients ...
#     await run_debate_logic(...)
#     # Assert query_grok was called and its result printed 