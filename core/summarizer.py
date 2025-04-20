import asyncio
from typing import List
import logging

from utils.models import Factor
from utils.prompts import SUMMARIZATION_PROMPT_TEMPLATE
# Use the default O4 client for summarization for now
# We could make the summarizer model configurable later if needed
from llm_clients.o4_client import query_o4
from rich.console import Console # Keep for final output

# Setup logger for this module
logger = logging.getLogger(__name__)
# Initialize Rich Console for final output
console = Console()

async def generate_summary(merged_factors: List[Factor]) -> str:
    """
    Generates a final prose summary based on the merged factors.

    Args:
        merged_factors: The list of ranked, filtered Factor objects from the merge step.

    Returns:
        A string containing the final prose summary.
    """
    if not merged_factors:
        return "No consensus factors were identified to generate a summary."

    # --- Format prompt context --- 
    consensus_details_lines = []
    all_justifications_lines = []
    for i, factor in enumerate(merged_factors):
        endorsements = getattr(factor, 'endorsement_count', 'N/A')
        consensus_details_lines.append(
            f"{i+1}. {factor.name} (Endorsements: {endorsements}, Mean Confidence: {factor.confidence:.2f})"
        )
        all_justifications_lines.append(f"Factor: {factor.name}\n{factor.justification}\n")
        
    consensus_factors_details = "\n".join(consensus_details_lines)
    all_justifications = "\n".join(all_justifications_lines)

    # --- Assemble and call LLM --- 
    prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(
        consensus_factors_details=consensus_factors_details,
        all_justifications=all_justifications
    )
    
    # Spinner handled in debate.py
    logger.info(f"Generating summary from {len(merged_factors)} merged factors.")

    # --- Added Print Statement ---
    console.print("\n--- [bold green]Factors Sent to Summarizer[/bold green] ---")
    console.print(merged_factors)
    console.print("--- End Factors for Summarizer ---\n")
    # --- End Added Print Statement ---

    # Format factors for the prompt
    # factors_str = _format_factors_for_summary(merged_factors)
    
    # logger.debug(f"Summarizer Prompt:\n{prompt[:500]}...")
    
    try:
        summary = await query_o4(prompt)
        logger.info(f"Summary generated successfully.")
        return summary
    except Exception as e:
        logger.error("Error during summarization query.", exc_info=True)
        return f"Error: Failed to generate summary. {e}"

# Example (for testing structure)
# async def main_test():
#     factors = [
#         Factor(name="A", justification="(Agent1): JA1\n(Agent2): JA2", confidence=4.5),
#         Factor(name="B", justification="(Agent1): JB1\n(Agent2): JB2", confidence=4.0)
#     ]
#     setattr(factors[0], 'endorsement_count', 2)
#     setattr(factors[1], 'endorsement_count', 2)
#     summary = await generate_summary(factors)
#     print("\nGenerated Summary:")
#     print(summary)

# if __name__ == "__main__":
#     asyncio.run(main_test()) 