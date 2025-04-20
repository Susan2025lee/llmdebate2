from typing import List, Dict, Optional
from collections import Counter, defaultdict
import statistics
import logging

from utils.models import Factor, AgentResponse
from rich.console import Console
console = Console()

# Setup logger for this module
logger = logging.getLogger(__name__)

def merge_factors(
    final_responses: Dict[str, AgentResponse], 
    min_endorsements: int = 2,
    min_confidence: float = 4.0,
    top_k: Optional[int] = None
) -> List[Factor]:
    """
    Merges factors from multiple agents based on endorsement count and mean confidence.

    Args:
        final_responses: Dictionary mapping agent names to their final AgentResponse.
        min_endorsements: Minimum number of agents required to endorse a factor.
        min_confidence: Minimum mean confidence score required for a factor if it doesn't 
                        meet the min_endorsements threshold.
        top_k: If set, return only the top K ranked factors.

    Returns:
        A ranked list of merged Factor objects.
    """
    endorsement_counts = Counter()
    confidence_scores = defaultdict(list)
    justifications = defaultdict(list)
    original_factors = defaultdict(list)

    # --- Step 1: Aggregate factors and stats --- 
    for agent_name, response in final_responses.items():
        unique_factors_this_agent = set() # Prevent agent from endorsing same factor multiple times
        for factor in response.factors:
            normalized_name = factor.name.strip().lower()
            if normalized_name in unique_factors_this_agent:
                continue # Already counted this factor for this agent
            unique_factors_this_agent.add(normalized_name)
            
            endorsement_counts[normalized_name] += 1
            confidence_scores[normalized_name].append(factor.confidence)
            justifications[normalized_name].append(f"({agent_name}): {factor.justification}")
            original_factors[normalized_name].append(factor) # Keep original factor object

    # --- Step 2: Calculate stats and filter --- 
    merged_factors = []
    for name, count in endorsement_counts.items():
        mean_conf = statistics.mean(confidence_scores[name]) if confidence_scores[name] else 0
        
        # Apply filtering logic
        if count >= min_endorsements or mean_conf >= min_confidence:
            # Combine justifications or select the best one?
            # For now, let's combine them, separated by newlines
            combined_justification = "\n".join(justifications[name])
            
            # Create a new Factor object representing the merged consensus
            merged_factor = Factor(
                name=original_factors[name][0].name, # Use original casing from first instance
                justification=combined_justification,
                confidence=float(mean_conf) # Ensure mean confidence is explicitly assigned
            )
            # Add endorsement count for sorting/ranking
            setattr(merged_factor, 'endorsement_count', count) 
            merged_factors.append(merged_factor)

    # --- Step 3: Rank factors --- 
    # Sort primarily by endorsement count (desc), secondarily by mean confidence (desc)
    merged_factors.sort(key=lambda f: (getattr(f, 'endorsement_count', 0), f.confidence), reverse=True)

    # --- Step 4: Trim to top K if specified --- 
    if top_k is not None and len(merged_factors) > top_k:
        merged_factors = merged_factors[:top_k]
        
    logger.info(f"Selected {len(merged_factors)} factors after merge/filter/rank.")
    # logger.debug(f"Merged Factors: {[f.name for f in merged_factors]}")

    # --- Added Print Statement ---
    console.print("\n--- [bold cyan]Final Merged & Ranked Factors[/bold cyan] ---")
    console.print(merged_factors)
    console.print("--- End Final Merged & Ranked Factors ---\n")
    # --- End Added Print Statement ---

    return merged_factors

# Example Usage (can be moved to tests later)
# if __name__ == '__main__':
#     f_a1 = Factor(name=" A ", justification="JA1", confidence=5)
#     f_b1 = Factor(name="B", justification="JB1", confidence=3)
#     f_c1 = Factor(name="C", justification="JC1", confidence=4)
#     resp1 = AgentResponse(agent_name="Agent1", factors=[f_a1, f_b1, f_c1])

#     f_a2 = Factor(name=" a ", justification="JA2", confidence=4)
#     f_b2 = Factor(name="B", justification="JB2", confidence=5)
#     f_d2 = Factor(name="D", justification="JD2", confidence=5)
#     resp2 = AgentResponse(agent_name="Agent2", factors=[f_a2, f_b2, f_d2])

#     f_a3 = Factor(name="A", justification="JA3", confidence=3)
#     f_e3 = Factor(name="E", justification="JE3", confidence=3) # Low confidence, low endorsement
#     resp3 = AgentResponse(agent_name="Agent3", factors=[f_a3, f_e3])
    
#     final_responses_example = {"Agent1": resp1, "Agent2": resp2, "Agent3": resp3}
    
#     merged = merge_factors(final_responses_example, top_k=3)
    
#     print("\nMerged Factors:")
#     for factor in merged:
#         print(f"- {factor.name} (Endorsements: {getattr(factor, 'endorsement_count')}, Mean Confidence: {factor.confidence:.2f})")
#         # print(f"  Justification: {factor.justification}")

# Expected output (approx): A, B, D (Factor C confidence is 4, Factor E endorsement=1, conf=3)
