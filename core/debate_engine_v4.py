# core/debate_engine_v4.py

import asyncio
import logging
from typing import Dict, Any, Callable, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import necessary prompts and client functions (adjust paths if needed)
from utils.prompts import FREEFORM_CRITIQUE_PROMPT_TEMPLATE
from llm_clients.o4_client import query_o4
from llm_clients.gemini_client import query_gemini

console = Console()
logger = logging.getLogger(__name__)

# Define agent query functions locally or import from a shared utility
AGENT_QUERY_FUNCTIONS = {
    "O4-mini": query_o4,
    "Gemini-2.5": query_gemini
}
try:
    from llm_clients.grok_client import query_grok # type: ignore
    AGENT_QUERY_FUNCTIONS["Grok-3"] = query_grok
except ImportError:
    pass # Grok is optional

async def run_freeform_critique_round(
    initial_baselines: Dict[str, str],
    question: str,
    progress_callback: Optional[Callable[[str, Any], None]]
) -> Dict[str, str]:
    """Runs the first round of free-form critique based on parallel baselines."""
    
    report_progress(progress_callback, "status", "Starting free-form critique round...", use_console=True)
    
    critique_tasks = []
    agent_names = list(AGENT_QUERY_FUNCTIONS.keys())
    prompt_details = {}

    for agent_name in agent_names:
        if agent_name not in initial_baselines or initial_baselines[agent_name].startswith("Error:"):
            logger.warning(f"Skipping critique for {agent_name} due to missing or failed baseline.")
            continue

        # Format other baselines for the prompt
        other_baselines_formatted = ""
        for other_agent, baseline_text in initial_baselines.items():
            if other_agent != agent_name:
                other_baselines_formatted += f"--- Baseline from Agent: {other_agent} ---\n{baseline_text}\n--- End Baseline from Agent: {other_agent} ---\n\n"
        
        critique_prompt = FREEFORM_CRITIQUE_PROMPT_TEMPLATE.format(
            question=question,
            your_baseline=initial_baselines[agent_name],
            other_baselines_formatted=other_baselines_formatted.strip()
        )
        prompt_details[agent_name] = critique_prompt # Store for potential logging
        
        query_func = AGENT_QUERY_FUNCTIONS[agent_name]
        critique_tasks.append(query_func(critique_prompt))
        logger.debug(f"Critique prompt prepared for {agent_name}")

    if not critique_tasks:
        report_progress(progress_callback, "error", "No valid baselines available to start critique round.", use_console=True)
        return {}
        
    critique_results_map: Dict[str, str] = {}
    valid_agent_names_for_critique = [name for name in agent_names if name in prompt_details] # Agents actually prompted

    report_progress(progress_callback, "status", f"Querying {len(valid_agent_names_for_critique)} agents for free-form critique...", use_console=False)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        task = progress.add_task("[yellow]Running free-form critique...", total=len(valid_agent_names_for_critique))
        critique_results_list = await asyncio.gather(*critique_tasks, return_exceptions=True)
        progress.update(task, completed=True, visible=False)

    report_progress(progress_callback, "status", "Processing free-form critique results...", use_console=True)
    for agent_name, result in zip(valid_agent_names_for_critique, critique_results_list):
        if isinstance(result, Exception):
            error_msg = f"Error during free-form critique from {agent_name}: {result}"
            report_progress(progress_callback, "agent_error", {"agent_name": agent_name, "error": error_msg}, use_console=True)
            logger.error(f"Agent {agent_name} failed critique round", exc_info=result)
            critique_results_map[agent_name] = f"Error: {result}"
        else:
            report_progress(progress_callback, "agent_status", f"Critique received from {agent_name}.", use_console=True)
            critique_results_map[agent_name] = result
            # Send individual critique results to UI
            report_progress(progress_callback, "freeform_critique", {"agent_name": agent_name, "critique_text": result}, use_console=False)

    report_progress(progress_callback, "status", "Free-form critique round complete.", use_console=True)
    return critique_results_map

# Helper function (can be moved to a shared utility later)
def report_progress(callback: Optional[Callable[[str, Any], None]], update_type: str, data: Any, use_console: bool = True):
    """Safely calls the progress callback or prints to console."""
    if callback:
        try:
            callback(update_type, data)
        except Exception as e:
            logger.error(f"Error in progress callback: {e}", exc_info=True)
            if use_console:
                console.print(f"[Callback Error] [{update_type.upper()}] {data}")
    elif use_console:
        console.print(f"[{update_type.upper()}] {data}") 