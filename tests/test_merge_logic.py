import pytest
import sys
import os
from typing import List, Dict, Optional

# Add project root to sys.path to allow importing 'core' and 'utils'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Modules to test
from core.merge_logic import merge_factors
from utils.models import Factor, AgentResponse

# --- Test Data Setup --- 

# Basic factors
F_A = Factor(name="A", justification="JA", confidence=5)
F_A2 = Factor(name="A", justification="JA", confidence=5) # Distinct object for Agent 2
F_A3 = Factor(name="A", justification="JA", confidence=3) # Distinct object for Agent 3 (lower conf)
F_B = Factor(name="B", justification="JB", confidence=4)
F_C = Factor(name="C", justification="JC", confidence=3)
F_D = Factor(name="D", justification="JD", confidence=5) # High confidence, low endorsement
F_E = Factor(name="E", justification="JE", confidence=2) # Low confidence, low endorsement

# Agent responses for testing
RESP_1 = AgentResponse(agent_name="Agent1", factors=[F_A, F_B, F_C])
RESP_2 = AgentResponse(agent_name="Agent2", factors=[F_A2, F_B, F_D]) # A, B endorsed; D has high conf
RESP_3 = AgentResponse(agent_name="Agent3", factors=[F_A3, F_E])       # A endorsed; E is weak

FINAL_RESPONSES_BASIC = {"Agent1": RESP_1, "Agent2": RESP_2, "Agent3": RESP_3}

# --- Test Cases --- 

def test_merge_basic_endorsement_and_confidence():
    """ Test standard merge logic: A, B endorsed >= 2; D conf >= 4. """
    merged = merge_factors(FINAL_RESPONSES_BASIC)
    merged_names = [f.name for f in merged]
    
    # Expected: A (3 endorsements), B (2 endorsements), D (1 endorsement, conf=5 >= 4)
    assert len(merged) == 3
    assert merged_names == ["A", "B", "D"] # Check ranking order (A>B>D)
    
    # Check details of A
    factor_a = next(f for f in merged if f.name == "A")
    assert getattr(factor_a, 'endorsement_count') == 3
    assert factor_a.confidence == pytest.approx((5 + 5 + 3) / 3) # Mean confidence
    assert "(Agent1): JA" in factor_a.justification
    assert "(Agent2): JA" in factor_a.justification
    assert "(Agent3): JA" in factor_a.justification
    
    # Check details of B
    factor_b = next(f for f in merged if f.name == "B")
    assert getattr(factor_b, 'endorsement_count') == 2
    assert factor_b.confidence == pytest.approx((4 + 4) / 2)
    assert "(Agent1): JB" in factor_b.justification
    assert "(Agent2): JB" in factor_b.justification
    
    # Check details of D
    factor_d = next(f for f in merged if f.name == "D")
    assert getattr(factor_d, 'endorsement_count') == 1
    assert factor_d.confidence == pytest.approx(5)
    assert "(Agent2): JD" in factor_d.justification

def test_merge_top_k_filtering():
    """ Test that top_k correctly limits the number of results. """
    merged = merge_factors(FINAL_RESPONSES_BASIC, top_k=2)
    merged_names = [f.name for f in merged]
    
    # Expected: A, B (top 2 ranked)
    assert len(merged) == 2
    assert merged_names == ["A", "B"]

def test_merge_stricter_thresholds():
    """ Test with higher thresholds, only A should pass. """
    merged = merge_factors(FINAL_RESPONSES_BASIC, min_endorsements=3, min_confidence=4.5)
    merged_names = [f.name for f in merged]
    
    # Expected: A (endorsement >= 3) and D (confidence >= 4.5)
    assert len(merged) == 2
    assert sorted(merged_names) == sorted(["A", "D"])

def test_merge_case_insensitivity_and_whitespace():
    """ Test that factors with different casing/whitespace are merged correctly. """
    f_a_lower = Factor(name=" a ", justification="JA_lower", confidence=4)
    f_b_space = Factor(name="B  ", justification="JB_space", confidence=5)
    
    resp_mixed = AgentResponse(agent_name="AgentMix", factors=[f_a_lower, f_b_space])
    final_responses_mixed = {"Agent1": RESP_1, "AgentMix": resp_mixed} # A endorsed, B endorsed
    
    merged = merge_factors(final_responses_mixed)
    merged_names = [f.name for f in merged]
    
    assert len(merged) == 2 # A and B should be merged
    assert "A" in merged_names
    assert "B" in merged_names
    
    factor_a = next(f for f in merged if f.name == "A")
    assert getattr(factor_a, 'endorsement_count') == 2
    assert "JA" in factor_a.justification
    assert "JA_lower" in factor_a.justification
    
    factor_b = next(f for f in merged if f.name == "B")
    assert getattr(factor_b, 'endorsement_count') == 2
    assert "JB" in factor_b.justification
    assert "JB_space" in factor_b.justification

def test_merge_no_responses():
    """ Test merging with an empty input dictionary. """
    merged = merge_factors({}) 
    assert len(merged) == 0

def test_merge_empty_factors():
    """ Test merging when agents return no factors. """
    resp_empty1 = AgentResponse(agent_name="Empty1", factors=[])
    resp_empty2 = AgentResponse(agent_name="Empty2", factors=[])
    merged = merge_factors({"E1": resp_empty1, "E2": resp_empty2})
    assert len(merged) == 0

def test_merge_no_consensus():
    """ Test merging when no factors meet the criteria. """
    f_x = Factor(name="X", justification="JX", confidence=1)
    f_y = Factor(name="Y", justification="JY", confidence=2)
    resp_weak1 = AgentResponse(agent_name="Weak1", factors=[f_x])
    resp_weak2 = AgentResponse(agent_name="Weak2", factors=[f_y])
    merged = merge_factors({"W1": resp_weak1, "W2": resp_weak2})
    assert len(merged) == 0 