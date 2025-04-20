import asyncio
import re
import json # <-- Added import
from typing import List, Dict, Optional
from rich.console import Console # Use Rich for printing
from rich.progress import Progress, SpinnerColumn, TextColumn # Added import
import logging

# from llm_clients.o4_client import query_o4
# from llm_clients.gemini_client import query_gemini
# from llm_clients.grok_client import query_grok # Keep commented out for now
from utils.models import Factor, AgentResponse
from utils.prompts import CRITIQUE_PROMPT_TEMPLATE
# import typer # <---- Remove this commented import

# Setup logger for this module
logger = logging.getLogger(__name__)

# Initialize Rich Console (or import from debate.py if preferred)
console = Console()

# Mapping from agent name to its query function
AGENT_QUERY_FUNCTIONS = {
    "O4-mini": "llm_clients.o4_client.query_o4", # Store paths for dynamic import/patching
    "Gemini-2.5": "llm_clients.gemini_client.query_gemini",
    # "Grok-3": query_grok, # Add back if Grok is included
}

AGENT_NAMES = list(AGENT_QUERY_FUNCTIONS.keys())

def _parse_factor_list(text: str) -> List[Factor]:
    """Parses the raw LLM output expecting a JSON array into a list of Factor objects."""
    factors = []
    raw_text = text # Keep original for logging if needed

    # Attempt to find the first JSON array block `[...]` using a non-greedy match.
    # This is more robust to surrounding text or markdown markers.
    match = re.search(r'(\[.*?\])', raw_text, re.DOTALL)
    
    if match:
        json_str = match.group(1)
    else:
        logger.warning(f"Could not find JSON array structure `[...]` in response: {raw_text[:200]}...")
        return []

    try:
        data = json.loads(json_str)
        if not isinstance(data, list):
            raise TypeError("Parsed JSON is not a list.")

        for item in data:
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dictionary item in JSON array: {item}")
                continue

            name = item.get('factor_name')
            justification = item.get('justification')
            confidence_raw = item.get('confidence')

            if not name or not justification or confidence_raw is None:
                logger.warning(f"Skipping factor with missing fields: {item}")
                continue

            try:
                confidence = float(confidence_raw)
                if not 1 <= confidence <= 5:
                     logger.warning(f"Clamping confidence {confidence} to range [1, 5] for factor '{name}'")
                     confidence = max(1.0, min(5.0, confidence))
            except (ValueError, TypeError):
                 logger.warning(f"Could not parse confidence '{confidence_raw}' as number for factor '{name}'. Skipping.")
                 continue
            
            factors.append(Factor(
                name=str(name), # Ensure name is string
                justification=str(justification), # Ensure justification is string
                confidence=confidence
            ))

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {e}\nRaw JSON string attempted: {json_str[:500]}...")
        return [] # Return empty list on JSON failure
    except TypeError as e:
         logger.error(f"Parsed JSON structure was unexpected: {e}\nRaw JSON string: {json_str[:500]}...")
         return []

    return factors

def _format_factors_for_prompt(factors: List[Factor]) -> str:
    """Formats a list of factors into a JSON string suitable for inclusion in a prompt."""
    if not factors:
        return "[]" # Return empty JSON array string
    
    factor_list_of_dicts = [
        {
            "factor_name": f.name,
            "justification": f.justification,
            "confidence": f.confidence
        }
        for f in factors
    ]
    
    try:
        # Use compact separators for potentially shorter prompt context
        return json.dumps(factor_list_of_dicts, separators=(',', ':'))
    except TypeError as e:
        logger.error(f"Failed to serialize factors to JSON: {e}")
        return "[]" # Return empty array on serialization error

def _check_convergence(
    current_round_responses: Dict[str, AgentResponse],
    previous_round_responses: Dict[str, AgentResponse],
    agent_names: List[str], # Pass the list of agents being considered
    confidence_threshold: float = 0.5 # How much confidence can change before it's considered a change
) -> bool:
    """Checks if the debate has converged based on changes in factors and confidences."""
    if not previous_round_responses: # Cannot check convergence on the first round
        return False

    # Iterate over agents present in the current round's responses
    for agent_name in agent_names:
        current_resp = current_round_responses.get(agent_name)
        prev_resp = previous_round_responses.get(agent_name)

        if not current_resp or not prev_resp:
            # If an agent errored or is missing, assume no convergence
            # Alternatively, could handle this differently (e.g., ignore missing agent)
            logger.warning(f"Agent {agent_name} response missing for convergence comparison. Assuming no convergence.")
            return False 

        # Compare sets of factor names (case-insensitive handled by Factor's hash/eq)
        current_factors_set = set(current_resp.factors)
        prev_factors_set = set(prev_resp.factors)

        if current_factors_set != prev_factors_set:
            logger.info(f"Convergence check: Agent {agent_name} changed factors.")
            # print(f"[DEBUG] Prev: {[f.name for f in prev_factors_set]}, Curr: {[f.name for f in current_factors_set]}")
            return False # Factors themselves changed

        # If factors are the same, check confidence levels
        prev_factors_dict = {f.name.strip().lower(): f for f in prev_resp.factors}
        for current_factor in current_resp.factors:
            prev_factor = prev_factors_dict.get(current_factor.name.strip().lower())
            # Should always find a match if sets were equal, but check defensively
            if prev_factor and abs(current_factor.confidence - prev_factor.confidence) > confidence_threshold:
                logger.info(f"Convergence check: Agent {agent_name} confidence changed for factor '{current_factor.name}'.")
                return False # Significant confidence change
                
    # If we looped through all agents without returning False, it converged
    logger.info("Convergence check: All agents stable. Convergence reached.")
    return True

async def run_debate_rounds(
    initial_responses: Dict[str, AgentResponse],
    question: str,
    max_rounds: int,
    human_feedback_callback: Optional[callable] = None
) -> List[Dict[str, AgentResponse]]:
    """Orchestrates the debate rounds."""
    # Import client functions here so patches work correctly during tests
    from llm_clients.o4_client import query_o4
    from llm_clients.gemini_client import query_gemini

    # Update the map now that imports are done
    _local_agent_query_functions = {
        "O4-mini": query_o4,
        "Gemini-2.5": query_gemini,
    }
    _agent_names = list(_local_agent_query_functions.keys())

    logger.info(f"Starting debate rounds for question: '{question[:50]}...'. Max rounds: {max_rounds}")
    debate_history: List[Dict[str, AgentResponse]] = [initial_responses]
    current_responses = initial_responses
    last_human_feedback = "None"

    for round_num in range(1, max_rounds + 1):
        console.print(f"\n[bold magenta]--- Round {round_num} ---[/bold magenta]\n")
        tasks = []
        round_prompts = {}

        # Get human feedback *before* assembling prompts for this round (but after round 1 results are shown)
        if human_feedback_callback and round_num > 1:
            human_feedback_input = human_feedback_callback()
            last_human_feedback = human_feedback_input if human_feedback_input else "None"
            console.print(f"([yellow]Human feedback for next round:[/yellow] '{last_human_feedback}')")
            logger.info(f"Human feedback provided for round {round_num}: '{last_human_feedback}'")

        # Prepare prompts for each agent
        for agent_name in _agent_names:
            previous_self_response = current_responses.get(agent_name)
            previous_factors_str = _format_factors_for_prompt(previous_self_response.factors) if previous_self_response else "N/A"
            
            other_agents_factors_list = []
            for other_name, other_response in current_responses.items():
                if other_name != agent_name:
                    other_agents_factors_list.append(f"Agent {other_name}:\n{_format_factors_for_prompt(other_response.factors)}")
            other_agents_factors_str = "\n\n".join(other_agents_factors_list) if other_agents_factors_list else "No other agent responses available."

            # Assemble the critique prompt
            critique_prompt = CRITIQUE_PROMPT_TEMPLATE.format(
                question=question,
                previous_factors=previous_factors_str,
                other_agents_factors=other_agents_factors_str,
                human_feedback=last_human_feedback
            )
            round_prompts[agent_name] = critique_prompt
            logger.debug(f"Prompt for {agent_name} in Round {round_num}:\n{critique_prompt[:300]}...")

            # Get the query function for the agent
            query_func = _local_agent_query_functions[agent_name]
            tasks.append(query_func(critique_prompt))

        # Execute agent queries in parallel
        # typer.secho(f"Querying agents for round {round_num}...", fg=typer.colors.YELLOW) # <-- Remove this commented line

        # Use Rich Progress for async tasks within the round
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            round_task = progress.add_task(f"[yellow]Querying agents for round {round_num}...", total=None)
            results = await asyncio.gather(*tasks, return_exceptions=True)
            progress.update(round_task, completed=True, visible=False)
        
        # Process results
        next_round_responses: Dict[str, AgentResponse] = {}
        for i, agent_name in enumerate(_agent_names):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Agent {agent_name} failed in round {round_num}", exc_info=result)
                # Keep previous response or handle error state
                next_round_responses[agent_name] = current_responses.get(agent_name, AgentResponse(agent_name=agent_name))
                next_round_responses[agent_name].raw_response = f"Error: {result}"
            else:
                raw_response_text = result
                console.print(f"\n--- [bold yellow]Raw Response from {agent_name} (Round {round_num})[/bold yellow] ---")
                console.print(raw_response_text)
                console.print(f"--- End Raw Response from {agent_name} ---\n")
                parsed_factors = _parse_factor_list(raw_response_text)
                console.print(f"[[bold blue]{agent_name}[/bold blue]] Parsed Factors (Round {round_num}): {len(parsed_factors)} factors")
                # print(f"Parsed factors for {agent_name}: {[f.name for f in parsed_factors]}") # Debug
                next_round_responses[agent_name] = AgentResponse(
                    agent_name=agent_name, 
                    factors=parsed_factors, 
                    raw_response=raw_response_text
                    # Critique field is not parsed/used yet
                )

        debate_history.append(next_round_responses)
        current_responses = next_round_responses

        # --- Convergence Check ---
        if round_num > 1: # Only check after the second round results are in
            previous_responses = debate_history[-2] # Get responses from the round just finished
            if _check_convergence(current_responses, previous_responses, agent_names=_agent_names):
                console.print("[bold green]Convergence detected. Ending debate early.[/bold green]")
                break # Exit the round loop

    console.print(f"\n[bold green]--- Debate completed after {round_num} rounds ---[/bold green]\n")
    logger.info(f"Debate completed after {round_num} rounds.")
    return debate_history

# Example usage (for testing structure, not functional yet)
# async def main_test():
#     initial = {
#         "O4-mini": AgentResponse(agent_name="O4-mini", factors=[Factor(name="A", justification="J_A", confidence=4)]),
#         "Gemini-2.5": AgentResponse(agent_name="Gemini-2.5", factors=[Factor(name="B", justification="J_B", confidence=3)])
#     }
#     history = await run_debate_rounds(initial, 2)
#     print(f"\nHistory length: {len(history)}")

# if __name__ == "__main__":
#     asyncio.run(main_test()) 