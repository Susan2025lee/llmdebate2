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
from judge.judge_agent import judge_quality, _parse_judge_ratings
from utils.prompts import JUDGE_PROMPT_TEMPLATE

# --- Test _parse_judge_ratings --- 

def test_parse_ratings_well_formed():
    text = """
    1. Completeness: Rating: [Better]
       Reasoning: More factors.
    2. Correctness: Rating: Equal
       Reasoning: Seems okay.
    3. Clarity: Rating: [Worse]
       Reasoning: Too verbose.
    """
    expected = {"Completeness": "Better", "Correctness": "Equal", "Clarity": "Worse"}
    assert _parse_judge_ratings(text) == expected

def test_parse_ratings_mixed_case_formats():
    text = "completeness: RATING: BETTER\ncorrectness: Rating: [equal]\nclarity: rating: worse"
    expected = {"Completeness": "Better", "Correctness": "Equal", "Clarity": "Worse"}
    assert _parse_judge_ratings(text) == expected

def test_parse_ratings_missing_dimension():
    text = "Completeness: Rating: Better\nClarity: Rating: Equal"
    # Expect Correctness to default to Equal
    expected = {"Completeness": "Better", "Correctness": "Equal", "Clarity": "Equal"}
    assert _parse_judge_ratings(text) == expected

def test_parse_ratings_empty_or_malformed():
    text1 = ""
    text2 = "No ratings found."
    expected = {"Completeness": "Equal", "Correctness": "Equal", "Clarity": "Equal"}
    assert _parse_judge_ratings(text1) == expected
    assert _parse_judge_ratings(text2) == expected

# --- Test judge_quality --- 

@pytest.mark.asyncio
@patch('judge.judge_agent.query_o4', new_callable=AsyncMock)
@patch('judge.judge_agent._parse_judge_ratings') # Mock parsing
@patch('judge.judge_agent.typer.secho') 
@patch('judge.judge_agent.typer.echo')
async def test_judge_accept_merged(mock_echo, mock_secho, mock_parse, mock_query_o4):
    """ Test judge accepts merged answer (Better/Equal ratings). """
    mock_raw_response = "Ratings: Better, Equal, Better"
    mock_parsed_ratings = {"Completeness": "Better", "Correctness": "Equal", "Clarity": "Better"}
    mock_query_o4.return_value = mock_raw_response
    mock_parse.return_value = mock_parsed_ratings
    
    baseline = "Base answer."
    merged = "Merged answer, much better."
    question = "Test question?"
    
    decision, ratings, raw = await judge_quality(baseline, merged, question)
    
    assert decision == "Accept Merged"
    assert ratings == mock_parsed_ratings
    assert raw == mock_raw_response
    mock_query_o4.assert_awaited_once() # Check LLM called
    mock_parse.assert_called_once_with(mock_raw_response) # Check parser called
    # Check prompt formatting (optional but good)
    expected_prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, baseline_answer=baseline, merged_answer=merged)
    assert mock_query_o4.call_args[0][0] == expected_prompt
    mock_secho.assert_any_call("Judge Decision: Accept Merged", fg='green')

@pytest.mark.asyncio
@patch('judge.judge_agent.query_o4', new_callable=AsyncMock)
@patch('judge.judge_agent._parse_judge_ratings')
@patch('judge.judge_agent.typer.secho') 
@patch('judge.judge_agent.typer.echo')
async def test_judge_fallback_to_baseline(mock_echo, mock_secho, mock_parse, mock_query_o4):
    """ Test judge recommends fallback (Worse rating found). """
    mock_raw_response = "Ratings: Better, Worse, Equal"
    mock_parsed_ratings = {"Completeness": "Better", "Correctness": "Worse", "Clarity": "Equal"}
    mock_query_o4.return_value = mock_raw_response
    mock_parse.return_value = mock_parsed_ratings
    
    decision, ratings, raw = await judge_quality("Base", "Merged", "Q")
    
    assert decision == "Fallback to Baseline"
    assert ratings == mock_parsed_ratings
    mock_query_o4.assert_awaited_once()
    mock_parse.assert_called_once_with(mock_raw_response)
    mock_secho.assert_any_call("Judge Decision: Fallback to Baseline (found 'Worse' rating)", fg='red')

@pytest.mark.asyncio
@patch('judge.judge_agent.query_o4', new_callable=AsyncMock)
@patch('judge.judge_agent._parse_judge_ratings')
@patch('judge.judge_agent.typer.secho') 
@patch('judge.judge_agent.typer.echo')
async def test_judge_parsing_error(mock_echo, mock_secho, mock_parse, mock_query_o4):
    """ Test judge handles parsing errors. """
    mock_raw_response = "Something went wrong, no ratings here."
    # Simulate parsing failure by returning a dict containing "Error"
    mock_parsed_ratings = {"Completeness": "Better", "Correctness": "Error", "Clarity": "Equal"} 
    mock_query_o4.return_value = mock_raw_response
    mock_parse.return_value = mock_parsed_ratings # Return the error dict
    
    decision, ratings, raw = await judge_quality("Base", "Merged", "Q")
    
    assert decision == "Error during parsing"
    assert ratings == mock_parsed_ratings # Returns the dict with error
    mock_secho.assert_any_call("Judge Decision: Error during parsing", fg='red')

@pytest.mark.asyncio
@patch('judge.judge_agent.query_o4', new_callable=AsyncMock)
@patch('judge.judge_agent.typer.secho') 
@patch('judge.judge_agent.typer.echo')
async def test_judge_llm_query_error(mock_echo, mock_secho, mock_query_o4):
    """ Test judge handles errors during the LLM call. """
    mock_exception = Exception("LLM Unavailable")
    mock_query_o4.side_effect = mock_exception
    
    decision, ratings, raw = await judge_quality("Base", "Merged", "Q")
    
    assert decision == "Error"
    assert ratings == {"Completeness": "Error", "Correctness": "Error", "Clarity": "Error"} # Default error ratings
    assert "Error: Failed to get judge response" in raw
    assert "LLM Unavailable" in raw

@pytest.mark.asyncio
async def test_judge_missing_input():
    """ Test judge handles missing baseline or merged answer. """
    decision, ratings, raw = await judge_quality("", "Merged", "Q")
    assert decision == "Error"
    assert "Missing baseline or merged answer" in raw
    
    decision, ratings, raw = await judge_quality("Base", "", "Q")
    assert decision == "Error"
    assert "Missing baseline or merged answer" in raw 