# core/synthesizer.py

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import necessary prompts and LLM interface
from utils.prompts import SYNTHESIS_PROMPT_TEMPLATE
# Assuming a high-capability model like O4-mini or a dedicated judge model for synthesis
# Using LLMInterface to handle client interaction and potential model selection via env vars
from llm_interface import LLMInterface 

console = Console()
logger = logging.getLogger(__name__)

# Helper function (copied from debate_engine_v4, consider moving to shared utility)
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

def _format_dict_for_prompt(data: Dict[str, str], title_prefix: str) -> str:
    """Formats a dictionary of agent responses for inclusion in the synthesis prompt."""
    formatted_text = ""
    for agent, text in data.items():
        formatted_text += f"--- {title_prefix} from Agent: {agent} ---\n{text}\n--- End {title_prefix} from Agent: {agent} ---\n\n"
    return formatted_text.strip()

def _format_debate_rounds_for_prompt(debate_rounds: List[Dict[str, Any]]) -> str:
    """Formats the list of debate round dictionaries for the synthesis prompt."""
    formatted_text = ""
    for round_data in debate_rounds:
        round_num = round_data.get("round", "Unknown")
        responses = round_data.get("responses", {})
        formatted_text += f"=== Debate Round {round_num} ===\n\n"
        formatted_text += _format_dict_for_prompt(responses, "Response")
        formatted_text += "\n\n"
    return formatted_text.strip()

async def synthesize_final_answer(
    question: str,
    initial_baselines: Dict[str, str],
    debate_rounds: List[Dict[str, Any]], # Expects list like [{"round": 1, "responses": {...}}] 
    progress_callback: Optional[Callable[[str, Any], None]]
) -> str:
    """Synthesizes the final answer using an LLM based on all baselines and debate text."""
    
    report_progress(progress_callback, "status", "Starting final answer synthesis...", use_console=True)

    # Determine the synthesizer model (e.g., could be configurable via env var)
    # Defaulting to a high-capability model like O4-mini for synthesis quality.
    synthesizer_model_key = "gpt-o4-mini" # Or read from os.getenv("SYNTHESIZER_MODEL_KEY", "gpt-o4-mini")
    try:
        # Initialize LLMInterface specifically for the synthesizer model
        synthesizer_llm = LLMInterface(model_key=synthesizer_model_key)
    except ValueError as e:
        msg = f"Error initializing synthesizer LLM ({synthesizer_model_key}): {e}"
        report_progress(progress_callback, "error", msg, use_console=True)
        return f"Error: Could not initialize synthesizer model. {e}"
    except Exception as e:
        msg = f"Unexpected error initializing synthesizer LLM: {e}"
        report_progress(progress_callback, "error", msg, use_console=True)
        logger.error("Unexpected error during synthesizer LLM init", exc_info=True)
        return f"Error: Could not initialize synthesizer model. {e}"

    # Format inputs for the prompt
    initial_baselines_formatted = _format_dict_for_prompt(initial_baselines, "Baseline")
    critique_texts_formatted = _format_debate_rounds_for_prompt(debate_rounds)

    synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        question=question,
        initial_baselines_formatted=initial_baselines_formatted,
        critique_texts_formatted=critique_texts_formatted
    )
    
    logger.debug(f"Synthesizer Prompt prepared for model {synthesizer_llm.model_name}:")
    # logger.debug(synthesis_prompt) # Uncomment for full prompt debugging

    final_answer = "Error: Synthesis failed."
    report_progress(progress_callback, "status", f"Querying synthesizer model ({synthesizer_llm.model_name})...", use_console=False)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        task = progress.add_task("[yellow]Synthesizing final answer...", total=None)
        try:
            # Use generate_response which handles system prompts appropriately if needed by the template in future
            final_answer = await asyncio.to_thread( # Use to_thread for potentially long sync call within async context
                synthesizer_llm.generate_response, 
                prompt=synthesis_prompt, # Pass the whole formatted content as the main prompt
                temperature=0.5 # Lower temp for more deterministic synthesis
            )
            report_progress(progress_callback, "status", "Synthesis complete.", use_console=True)
        except Exception as e:
            msg = f"Error during synthesis call: {e}"
            report_progress(progress_callback, "error", msg, use_console=True)
            logger.error("Synthesizer LLM call failed", exc_info=True)
            final_answer = f"Error: Synthesis failed due to LLM error: {e}" # Update answer on error
        finally:
            progress.update(task, completed=True, visible=False)
            # Clean up LLM interface if needed (though current OpenAI client might not require it)
            try:
                synthesizer_llm.close()
            except Exception as e:
                logger.warning(f"Ignoring error during synthesizer LLM close: {e}")

    return final_answer 