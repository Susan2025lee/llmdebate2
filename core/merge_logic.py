import asyncio
import json
from typing import List, Dict, Optional
from collections import Counter, defaultdict
import statistics
import logging

from utils.models import Factor, AgentResponse
# Import prompts from the central file
from utils.prompts import MERGE_FACTORS_PROMPT, REFINE_PROMPT_TEMPLATE
from rich.console import Console
# Assuming LLMInterface is correctly importable from the root or adjusted path
from llm_interface import LLMInterface

console = Console()
logger = logging.getLogger(__name__)

# --- LLM-based Merge Prompt Template --- 
# Definition moved to utils/prompts.py

# --- V3: Refinement Prompt Template --- 
# Definition moved to utils/prompts.py

async def merge_factors(
    final_responses: Dict[str, AgentResponse], 
    question: str,
    top_k: Optional[int] = 5 # Default top_k to 5
) -> List[Factor]:
    """
    Merges factors from multiple agents using an LLM call for semantic synthesis and ranking.

    Args:
        final_responses: Dictionary mapping agent names to their final AgentResponse.
        question: The original question being debated.
        top_k: Return only the top K ranked synthesized factors.

    Returns:
        A list of synthesized Factor objects, ranked by the LLM.
    """
    logger.info(f"Starting LLM-based factor merging for top {top_k} factors.")

    # --- Step 1: Format Factors for Prompt --- 
    formatted_factors_list = []
    all_original_factors = [] # Keep track for debugging or potential future use
    for agent_name, response in final_responses.items():
        if not response.factors:
            continue # Skip agents with no factors
        agent_header = f"Factors from {agent_name}:"
        formatted_factors_list.append(agent_header)
        for factor in response.factors:
            all_original_factors.append(factor)
            factor_str = (
                f"  - Factor: \"{factor.name}\" (Confidence: {factor.confidence:.1f})\n"
                f"    Justification: {factor.justification}"
            )
            formatted_factors_list.append(factor_str)
        formatted_factors_list.append("") # Add a blank line between agents
    
    formatted_factors_text = "\n".join(formatted_factors_list).strip()

    if not formatted_factors_text:
        logger.warning("No factors found in final responses to merge.")
        return []

    # --- Step 2: Prepare and Call LLM --- 
    # TODO: Consider which model to use for merging (config?) - Defaulting for now
    #       Might need a higher capability model for good synthesis.
    #       Using the default model configured in LLMInterface for now.
    merge_llm = LLMInterface() # Uses default model from env/config

    prompt = MERGE_FACTORS_PROMPT.format(
        question=question,
        top_k=top_k,
        formatted_factors=formatted_factors_text
    )
    
    logger.debug(f"Merge Prompt (first 500 chars):\n{prompt[:500]}...")
    
    # Assuming LLMInterface has an async generate_response or similar method
    # If using generate_chat_response, adapt message format
    try:
        # Using generate_response as it's simpler for a single prompt->response task
        raw_llm_response = await asyncio.to_thread(merge_llm.generate_response, prompt)
        logger.debug(f"Raw Merge LLM Response:\n{raw_llm_response}")
    except Exception as e:
        logger.error(f"Error calling LLM for factor merging: {e}", exc_info=True)
        console.print(f"[bold red]Error calling LLM for merging: {e}[/bold red]")
        return [] # Return empty list on LLM error

    # --- Step 3: Parse LLM Output --- 
    merged_factors: List[Factor] = []
    try:
        # Basic parsing: Assume LLM returns just the JSON list
        # More robust parsing might involve regex to find JSON block
        parsed_json = json.loads(raw_llm_response)
        
        if not isinstance(parsed_json, list):
            raise ValueError("LLM response is not a JSON list.")

        for item in parsed_json:
            if isinstance(item, dict) and 'name' in item and 'justification' in item and 'confidence' in item:
                # Validate confidence format if necessary
                try:
                    confidence_val = float(item['confidence'])
                except ValueError:
                    logger.warning(f"Could not parse confidence '{item['confidence']}' as float for factor '{item['name']}'. Skipping.")
                    continue
                
                merged_factors.append(Factor(
                    name=str(item['name']),
                    justification=str(item['justification']),
                    confidence=confidence_val
                ))
            else:
                logger.warning(f"Skipping invalid item in LLM JSON response: {item}")
        
        # Ensure we don't exceed top_k even if LLM returns more
        if top_k is not None and len(merged_factors) > top_k:
             logger.warning(f"LLM returned {len(merged_factors)} factors, trimming to top {top_k}.")
             merged_factors = merged_factors[:top_k]

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from LLM: {e}")
        logger.error(f"LLM Response was: {raw_llm_response}")
        console.print(f"[bold red]Error: Failed to parse merge response from LLM.[/bold red]")
        # Optionally, try regex extraction here as a fallback
        return [] # Return empty on parsing error
    except Exception as e:
        logger.error(f"Error processing LLM merge response: {e}", exc_info=True)
        console.print(f"[bold red]Error: Unexpected issue processing merge response: {e}[/bold red]")
        return []

    logger.info(f"Successfully merged and parsed {len(merged_factors)} factors from LLM.")
    console.print("\n--- [bold cyan]LLM Synthesized & Ranked Factors[/bold cyan] ---")
    if merged_factors:
        for factor in merged_factors:
             console.print(f"- [bold magenta]{factor.name}[/bold magenta] (Confidence: {factor.confidence:.2f})")
             console.print(f"  Justification: {factor.justification}") # Print justification too
    else:
        console.print("[yellow]LLM did not return any valid factors.[/yellow]")
    console.print("--- End LLM Synthesized & Ranked Factors ---\n")

    return merged_factors

async def refine_with_debate_summary(
    baseline_prose: str,
    debate_summary: str,
    question: str
) -> str:
    """
    Uses an LLM to integrate insights from a debate summary into an original baseline answer.

    Args:
        baseline_prose: The original prose answer generated by the anchor agent.
        debate_summary: The prose summary generated from the merged debate factors.
        question: The original question being debated.

    Returns:
        The refined prose answer, integrating baseline and debate insights.
    """
    logger.info("Starting V3 refinement: Integrating debate summary into baseline.")
    
    # TODO: Consider which model to use for refinement (config?) - Defaulting for now
    refine_llm = LLMInterface() # Uses default model from env/config
    
    prompt = REFINE_PROMPT_TEMPLATE.format(
        question=question,
        baseline_prose=baseline_prose,
        debate_summary=debate_summary
    )
    
    logger.debug(f"Refinement Prompt (first 500 chars):\n{prompt[:500]}...")
    
    try:
        refined_answer = await asyncio.to_thread(refine_llm.generate_response, prompt)
        logger.debug(f"Raw Refinement LLM Response:\n{refined_answer}")
        logger.info("Successfully generated refined answer.")
        # Simple return for now, add validation/parsing if output format becomes complex
        return refined_answer.strip()
    except Exception as e:
        logger.error(f"Error calling LLM for refinement: {e}", exc_info=True)
        console.print(f"[bold red]Error calling LLM for refinement: {e}[/bold red]")
        # Fallback: Return the original baseline if refinement fails?
        # Or maybe the debate summary? Returning baseline seems safer.
        console.print("[yellow]Refinement failed. Falling back to original baseline for this step.[/yellow]")
        return baseline_prose

# Remove old example usage if it exists
