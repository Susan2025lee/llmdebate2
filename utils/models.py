from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Factor:
    """Represents a single factor identified by an LLM agent."""
    name: str
    justification: str
    confidence: float # Store mean confidence after merge

    def __hash__(self):
        # Allow factors to be used in sets/dictionaries based on name
        return hash(self.name.strip().lower())

    def __eq__(self, other):
        # Factors are considered equal if their names match (case-insensitive)
        if not isinstance(other, Factor):
            return NotImplemented
        return self.name.strip().lower() == other.name.strip().lower()

@dataclass
class AgentResponse:
    """Represents the structured output from an agent in a single round."""
    agent_name: str
    factors: List[Factor] = field(default_factory=list)
    critique: Optional[str] = None # Critique of others' factors from previous round
    raw_response: Optional[str] = None # Store the raw LLM output for debugging/logging

# Example Usage:
# factor1 = Factor(name="Battery Tech", justification="Key enabler", confidence=5)
# factor2 = Factor(name=" Charging Infrastructure ", justification="Range anxiety", confidence=4)
# response = AgentResponse(agent_name="O4-mini", factors=[factor1, factor2]) 