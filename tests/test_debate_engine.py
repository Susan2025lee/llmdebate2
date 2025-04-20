import pytest
import asyncio
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock, call
from typing import List, Dict, Optional
import json

# Add project root to sys.path to allow importing 'core' and 'utils'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Modules to test
from core.debate_engine import run_debate_rounds, _check_convergence, _parse_factor_list
from utils.models import Factor, AgentResponse

# Mock agent responses for different scenarios
AGENT_1_R1_FACTORS = [Factor(name="A", justification="J_A", confidence=4), Factor(name="B", justification="J_B", confidence=3)]
AGENT_2_R1_FACTORS = [Factor(name="A", justification="J_A2", confidence=5), Factor(name="C", justification="J_C", confidence=2)]

AGENT_1_R2_FACTORS_NO_CHANGE = AGENT_1_R1_FACTORS
AGENT_2_R2_FACTORS_NO_CHANGE = AGENT_2_R1_FACTORS

AGENT_1_R2_FACTORS_CONV = [Factor(name="A", justification="J_A", confidence=4), Factor(name="B", justification="J_B", confidence=3)] # Same
AGENT_2_R2_FACTORS_CONV = [Factor(name="A", justification="J_A2", confidence=4.8), Factor(name="C", justification="J_C", confidence=2.1)] # Slight confidence change, within threshold

AGENT_1_R2_FACTORS_DIFF = [Factor(name="A", justification="J_A_revised", confidence=5), Factor(name="D", justification="J_D", confidence=4)] # Changed factors
AGENT_2_R2_FACTORS_DIFF = [Factor(name="A", justification="J_A2", confidence=5), Factor(name="C", justification="J_C_new", confidence=1)] # Changed justification/confidence

# Helper to create mock raw text responses that _parse_factor_list can handle
def _create_mock_response_text(factors: List[Factor]) -> str:
    lines = []
    for f in factors:
        lines.append(f"Factor Name: {f.name}\nJustification: {f.justification}\nConfidence: {f.confidence}")
    return "\n\n".join(lines)

# --- Test _check_convergence directly --- 

def test_convergence_check_no_prev():
    curr = {"A1": AgentResponse(agent_name="A1", factors=AGENT_1_R1_FACTORS)}
    assert not _check_convergence(curr, {}, agent_names=["A1"])

def test_convergence_check_factors_changed():
    prev = {"A1": AgentResponse(agent_name="A1", factors=AGENT_1_R1_FACTORS)}
    curr = {"A1": AgentResponse(agent_name="A1", factors=AGENT_1_R2_FACTORS_DIFF)}
    assert not _check_convergence(curr, prev, agent_names=["A1"])

def test_convergence_check_confidence_changed_significantly():
    prev = {"A1": AgentResponse(agent_name="A1", factors=[Factor('X', 'JX', 3)])}
    curr = {"A1": AgentResponse(agent_name="A1", factors=[Factor('X', 'JX', 4)])}
    assert not _check_convergence(curr, prev, agent_names=["A1"], confidence_threshold=0.5)

def test_convergence_check_confidence_stable():
    prev = {"A1": AgentResponse(agent_name="A1", factors=[Factor('X', 'JX', 3)])}
    curr = {"A1": AgentResponse(agent_name="A1", factors=[Factor('X', 'JX', 3.2)])}
    assert _check_convergence(curr, prev, agent_names=["A1"], confidence_threshold=0.5)

def test_convergence_check_stable_multi_agent():
    prev = {
        "A1": AgentResponse(agent_name="A1", factors=AGENT_1_R1_FACTORS),
        "A2": AgentResponse(agent_name="A2", factors=AGENT_2_R1_FACTORS)
    }
    curr = {
        "A1": AgentResponse(agent_name="A1", factors=AGENT_1_R2_FACTORS_CONV),
        "A2": AgentResponse(agent_name="A2", factors=AGENT_2_R2_FACTORS_CONV)
    }
    assert _check_convergence(curr, prev, agent_names=["A1", "A2"], confidence_threshold=0.5)

# --- Test run_debate_rounds --- 

@pytest.mark.asyncio
@patch('llm_clients.o4_client.query_o4', new_callable=AsyncMock)
@patch('llm_clients.gemini_client.query_gemini', new_callable=AsyncMock)
@patch('core.debate_engine._parse_factor_list') # Mock parsing to control factors directly
async def test_run_debate_rounds_max_rounds_reached(mock_parse, mock_query_gemini_patched, mock_query_o4_patched):
    """ Test debate runs for max_rounds when no convergence happens. """
    max_rounds = 2
    # Mock responses for 2 rounds (agent 1 changes, agent 2 doesn't)
    mock_query_o4_patched.side_effect = ["O4_R1_RAW", "O4_R2_RAW"] 
    mock_query_gemini_patched.side_effect = ["G_R1_RAW", "G_R2_RAW"]
    # Mock parsing results
    mock_parse.side_effect = [AGENT_1_R1_FACTORS, AGENT_2_R1_FACTORS, AGENT_1_R2_FACTORS_DIFF, AGENT_2_R1_FACTORS] 

    initial_responses = {
        "O4-mini": AgentResponse(agent_name="O4-mini", factors=[], raw_response="Initial O4"),
        "Gemini-2.5": AgentResponse(agent_name="Gemini-2.5", factors=[], raw_response="Initial Gemini")
    }
    mock_feedback_callback = MagicMock(return_value="") # No feedback

    history = await run_debate_rounds(
        initial_responses=initial_responses, 
        question="Test Question Max Rounds", # Pass a string question
        max_rounds=max_rounds, 
        human_feedback_callback=mock_feedback_callback
    )

    assert len(history) == max_rounds + 1 # Initial + 2 rounds
    assert mock_query_o4_patched.await_count == max_rounds
    assert mock_query_gemini_patched.await_count == max_rounds
    assert mock_feedback_callback.call_count == 1 # Called once before round 2
    # Check final completion message mentions correct number of rounds
    # Cannot assert on secho/echo mocks anymore
    # mock_secho.assert_any_call(f"\n--- Debate completed after {max_rounds} rounds --- \n", fg='green')

@pytest.mark.asyncio
@patch('llm_clients.o4_client.query_o4', new_callable=AsyncMock)
@patch('llm_clients.gemini_client.query_gemini', new_callable=AsyncMock)
@patch('core.debate_engine._parse_factor_list')
async def test_run_debate_rounds_convergence(mock_parse, mock_query_gemini_patched, mock_query_o4_patched):
    """ Test debate stops early due to convergence. """
    max_rounds = 3
    # R1 -> R2: No change. Convergence should happen after R2.
    mock_query_o4_patched.side_effect = ["O4_R1_RAW", "O4_R2_RAW"] 
    mock_query_gemini_patched.side_effect = ["G_R1_RAW", "G_R2_RAW"]
    mock_parse.side_effect = [AGENT_1_R1_FACTORS, AGENT_2_R1_FACTORS, AGENT_1_R2_FACTORS_CONV, AGENT_2_R2_FACTORS_CONV]

    initial_responses = {
        "O4-mini": AgentResponse(agent_name="O4-mini", factors=[]),
        "Gemini-2.5": AgentResponse(agent_name="Gemini-2.5", factors=[])
    }
    mock_feedback_callback = MagicMock(return_value="")

    history = await run_debate_rounds(
        initial_responses=initial_responses, 
        question="Test Question Convergence", # Pass a string question
        max_rounds=max_rounds, 
        human_feedback_callback=mock_feedback_callback
    )

    assert len(history) == 2 + 1 # Initial + 2 rounds (converged after R2)
    assert mock_query_o4_patched.await_count == 2
    assert mock_query_gemini_patched.await_count == 2
    assert mock_feedback_callback.call_count == 1 # Called once before round 2
    # Cannot assert on secho/echo mocks anymore
    # mock_secho.assert_any_call("Convergence detected. Ending debate early.", fg='green')
    # mock_secho.assert_any_call("\n--- Debate completed after 2 rounds --- \n", fg='green') # Completed after round 2

@pytest.mark.asyncio
@patch('llm_clients.o4_client.query_o4', new_callable=AsyncMock)
@patch('llm_clients.gemini_client.query_gemini', new_callable=AsyncMock)
@patch('core.debate_engine.CRITIQUE_PROMPT_TEMPLATE') # Patch the template string itself
@patch('core.debate_engine._parse_factor_list')
async def test_run_debate_rounds_human_feedback(mock_parse, mock_template, mock_query_gemini_patched, mock_query_o4_patched):
    """ Test that human feedback is collected and included in the prompt. """
    max_rounds = 2
    human_input = "Consider factor Z."
    # Mock responses for 2 rounds
    mock_query_o4_patched.side_effect = ["O4_R1_RAW", "O4_R2_RAW"]
    mock_query_gemini_patched.side_effect = ["G_R1_RAW", "G_R2_RAW"]
    mock_parse.side_effect = [AGENT_1_R1_FACTORS, AGENT_2_R1_FACTORS, AGENT_1_R2_FACTORS_DIFF, AGENT_2_R1_FACTORS]
    # Mock the template format method to capture args
    mock_template.format = MagicMock()

    initial_responses = {
        "O4-mini": AgentResponse(agent_name="O4-mini", factors=[]),
        "Gemini-2.5": AgentResponse(agent_name="Gemini-2.5", factors=[])
    }
    # Mock callback to return specific input
    mock_feedback_callback = MagicMock(return_value=human_input)

    await run_debate_rounds(
        initial_responses=initial_responses, 
        question="Test Question Feedback", # Pass a string question
        max_rounds=max_rounds, 
        human_feedback_callback=mock_feedback_callback
    )

    assert mock_feedback_callback.call_count == 1 # Called once before round 2
    
    # Check the arguments passed to the prompt template's format method in Round 2
    # It's called once per agent per round (2 agents * 2 rounds)
    assert mock_template.format.call_count == max_rounds * len(initial_responses) # 2 * 2 = 4
    # Get the keyword arguments from the *last* call to format (doesn't matter which agent for this check)
    format_kwargs = mock_template.format.call_args.kwargs
    # print(f"Format kwargs: {format_kwargs}") # Debug
    assert format_kwargs['human_feedback'] == human_input

# --- Test Cases for _parse_factor_list --- 

# Define test data needed for the original list parser tests
def create_json_string(data) -> str:
    "Helper to create a valid JSON string from a Python list/dict."
    return json.dumps(data, indent=2)

VALID_JSON_DATA = [
  {
    "factor_name": "Factor One",
    "justification": "Justification 1.",
    "confidence": 5
  },
  {
    "factor_name": "Factor Two",
    "justification": "Justification 2.",
    "confidence": 3.5
  }
]
VALID_JSON_STRING = create_json_string(VALID_JSON_DATA)

JSON_WITH_MARKDOWN_DATA = [
  {
    "factor_name": "Markdown Factor",
    "justification": "Wrapped in markdown.",
    "confidence": 4
  }
]
JSON_WITH_MARKDOWN = f"```json\n{create_json_string(JSON_WITH_MARKDOWN_DATA)}\n```"

JSON_WITH_SURROUNDING_TEXT_DATA = [
  {
    "factor_name": "Surrounded Factor",
    "justification": "Text before and after.",
    "confidence": 2
  }
]
JSON_WITH_SURROUNDING_TEXT = f"Okay, here is the JSON you requested:\n{create_json_string(JSON_WITH_SURROUNDING_TEXT_DATA)}\nThanks!"

JSON_WITH_EXTRA_WHITESPACE_DATA = [
  {
    "factor_name": "Whitespace Factor",
    "justification": "Lots of space.",
    "confidence": 1.0
  }
]
JSON_WITH_EXTRA_WHITESPACE = f"  \n\n{create_json_string(JSON_WITH_EXTRA_WHITESPACE_DATA)}\n\n  \n"

JSON_MISSING_FIELDS_DATA = [
  {
    "factor_name": "Good Factor",
    "justification": "Complete.",
    "confidence": 5
  },
  {
    "factor_name": "Missing Justification",
    "confidence": 4
  },
  {
    "justification": "Missing Name",
    "confidence": 3
  },
  {
    "factor_name": "Missing Confidence",
    "justification": "Not confident."
  }
]
JSON_MISSING_FIELDS = create_json_string(JSON_MISSING_FIELDS_DATA)

JSON_INVALID_CONFIDENCE_TYPE_DATA = [
  {
    "factor_name": "String Confidence",
    "justification": "Should be number.",
    "confidence": "4" # Confidence as string
  },
  {
    "factor_name": "Bad Confidence",
    "justification": "Cannot parse.",
    "confidence": "high" # Non-numeric string confidence
  }
]
JSON_INVALID_CONFIDENCE_TYPE = create_json_string(JSON_INVALID_CONFIDENCE_TYPE_DATA)

JSON_CONFIDENCE_OUT_OF_RANGE_DATA = [
  {
    "factor_name": "Too High",
    "justification": "Confidence > 5",
    "confidence": 6.0
  },
  {
    "factor_name": "Too Low",
    "justification": "Confidence < 1",
    "confidence": 0.5
  }
]
JSON_CONFIDENCE_OUT_OF_RANGE = create_json_string(JSON_CONFIDENCE_OUT_OF_RANGE_DATA)

# For malformed/invalid structure, keep the manual strings
INVALID_JSON_STRUCTURE = '''
{{
  "factor_name": "Not An Array",
  "justification": "This is an object.",
  "confidence": 3
}}
'''

MALFORMED_JSON_STRING = '''
[
  {{
    "factor_name": "Missing Comma"
    "justification": "Syntax error.",
    "confidence": 2
  }}
]
'''

NO_JSON_STRING = '''
This response does not contain any JSON array.
Factor Name: Old Style Factor
Justification: Some text.
Confidence: 3
'''

EMPTY_STRING = ""
EMPTY_JSON_ARRAY = "[]"

@pytest.mark.parametrize(
    "input_text, expected_factors",
    [
        # Happy Paths
        (VALID_JSON_STRING, [
            Factor(name="Factor One", justification="Justification 1.", confidence=5.0),
            Factor(name="Factor Two", justification="Justification 2.", confidence=3.5)
        ]),
        (JSON_WITH_MARKDOWN, [
            Factor(name="Markdown Factor", justification="Wrapped in markdown.", confidence=4.0)
        ]),
        # Handling variations
        (JSON_WITH_SURROUNDING_TEXT, [
            Factor(name="Surrounded Factor", justification="Text before and after.", confidence=2.0)
        ]),
        (JSON_WITH_EXTRA_WHITESPACE, [
             Factor(name="Whitespace Factor", justification="Lots of space.", confidence=1.0)
        ]),
         (EMPTY_JSON_ARRAY, []), # Empty list is valid
        # Error Handling & Edge Cases
        (JSON_MISSING_FIELDS, [ # Only the first factor is valid - others lack required fields
            Factor(name="Good Factor", justification="Complete.", confidence=5.0)
        ]),
        (JSON_INVALID_CONFIDENCE_TYPE, [ # First factor confidence is parsed from string "4", second ("high") is skipped
             Factor(name="String Confidence", justification="Should be number.", confidence=4.0)
        ]),
        (JSON_CONFIDENCE_OUT_OF_RANGE, [ # Confidences should be clamped
            Factor(name="Too High", justification="Confidence > 5", confidence=5.0),
            Factor(name="Too Low", justification="Confidence < 1", confidence=1.0)
        ]),
        (INVALID_JSON_STRUCTURE, []), # Not a list
        (MALFORMED_JSON_STRING, []), # JSONDecodeError due to missing comma
        (NO_JSON_STRING, []), # No JSON found
        (EMPTY_STRING, []), # Empty input
    ]
)
def test_parse_factor_list(input_text, expected_factors):
    """Tests the _parse_factor_list function with various inputs."""
    parsed_factors = _parse_factor_list(input_text)
    # Compare factor lists element by element for better diffs
    assert len(parsed_factors) == len(expected_factors)
    for parsed, expected in zip(parsed_factors, expected_factors):
        assert parsed.name == expected.name
        assert parsed.justification == expected.justification
        # Use pytest.approx for float comparison
        assert parsed.confidence == pytest.approx(expected.confidence)