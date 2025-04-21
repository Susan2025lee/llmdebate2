#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import typer
import asyncio
from typing import Dict, Any, Callable, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import logging
from utils.logger import setup_logger
import json
# LLM Interface is not directly used here anymore, but clients might use it
from llm_interface import LLMInterface

# Load environment variables
load_dotenv()

# Import core engine and models/prompts
from core.debate_engine import run_debate_rounds, _parse_factor_list
from core.merge_logic import merge_factors, refine_with_debate_summary
from core.summarizer import generate_summary
from judge.judge_agent import judge_quality
from utils.models import AgentResponse, Factor # For type hints and parsing
# Update imports for V2 prompts
from utils.prompts import (
    BASELINE_PROMPT_TEMPLATE, # Keep for reference/comparison if needed
    PROSE_BASELINE_GENERATION_TEMPLATE, 
    CRITIQUE_PROSE_BASELINE_TEMPLATE,
    FREEFORM_CRITIQUE_PROMPT_TEMPLATE,
    SYNTHESIS_PROMPT_TEMPLATE,
    REFINE_PROMPT_TEMPLATE
)
from core.debate_engine_v4 import run_freeform_critique_round
from core.synthesizer import synthesize_final_answer

# Initialize Rich Console
console = Console()

app = typer.Typer()

# Helper to safely call the callback or print to console
def report_progress(callback: Optional[Callable[[str, Any], None]], update_type: str, data: Any, use_console: bool = True):
    if callback:
        try:
            callback(update_type, data)
        except Exception as e:
            logging.error(f"Error in progress callback: {e}", exc_info=True)
            if use_console:
                console.print(f"[Callback Error] [{update_type.upper()}] {data}") 
    elif use_console:
        console.print(f"[{update_type.upper()}] {data}")

async def run_debate_logic(
    question: str, 
    max_rounds: int,
    output: Optional[str],
    verbose: bool,
    progress_callback: Optional[Callable[[str, Any], None]] = None,
    human_feedback_callback: Optional[Callable[[], str]] = None,
    synthesizer_choice: Optional[str] = "v4_default"
):
    """Core async logic for V4: Parallel Baselines & Free-Form Debate."""
    report_progress(progress_callback, "status", f"Starting V4 debate for: {question}", use_console=True)

    # --- Determine Synthesizer Type from Parameter --- #
    # Use the provided synthesizer_choice, default if None or invalid
    if synthesizer_choice not in ["v4_default", "v3_refine"]:
        logging.warning(f"Invalid synthesizer_choice '{synthesizer_choice}' received. Defaulting to 'v4_default'.")
        synthesizer_choice = "v4_default"
        
    synthesizer_type_log = "V3 Refine Style" if synthesizer_choice == "v3_refine" else "V4 Default Style"
    report_progress(progress_callback, "status", f"Using Synthesizer: {synthesizer_type_log}", use_console=True)

    # --- Transcript Data (V4 Structure) --- 
    transcript_data: Dict[str, Any] = {
        "version": "v4",
        "question": question,
        "parameters": {
            "max_rounds": max_rounds,
            "verbose": verbose,
            "output_file": output,
            "synthesizer_type": synthesizer_choice # Log the chosen synthesizer
        },
        "initial_prose_baselines": {}, # Dict[agent_name, prose_text]
        "debate_rounds": [], # List of round dicts: {"round": N, "responses": Dict[agent_name, text]}
        "final_synthesized_answer": "",
        "judge_result": {},
        "final_decision": "", # Based on judge vs. synthesized answer
        "final_answer": "" # The answer selected after judging
    }

    # --- V4 Step 1: Generate Parallel Prose Baselines --- 
    from llm_clients.o4_client import query_o4
    from llm_clients.gemini_client import query_gemini
    agent_query_functions = {
        "O4-mini": query_o4,
        "Gemini-2.5": query_gemini
    }
    try:
        from llm_clients.grok_client import query_grok # type: ignore
        agent_query_functions["Grok-3"] = query_grok
    except ImportError:
        pass # Grok is optional
    
    agent_names = list(agent_query_functions.keys())
    prose_baseline_prompt = PROSE_BASELINE_GENERATION_TEMPLATE.format(question=question)
    # Log the common prompt used
    transcript_data["parameters"]["prose_baseline_prompt"] = prose_baseline_prompt 

    baseline_tasks = []
    report_progress(progress_callback, "status", f"Querying {len(agent_names)} agents for parallel prose baselines...", use_console=False)
    for agent_name, query_func in agent_query_functions.items():
        baseline_tasks.append(query_func(prose_baseline_prompt))
    
    initial_baselines_results = {}
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        task = progress.add_task(f"[yellow]Generating parallel baselines...", total=len(agent_names))
        baseline_results_list = await asyncio.gather(*baseline_tasks, return_exceptions=True)
        progress.update(task, completed=True, visible=False)
        
    report_progress(progress_callback, "status", "Processing parallel baselines...", use_console=True)
    initial_baselines: Dict[str, str] = {}
    has_any_baseline_succeeded = False
    for agent_name, result in zip(agent_names, baseline_results_list):
        if isinstance(result, Exception):
            error_msg = f"Error generating baseline from {agent_name}: {result}"
            report_progress(progress_callback, "agent_error", {"agent_name": agent_name, "error": error_msg}, use_console=True)
            logging.error(f"Failed to generate baseline from {agent_name}", exc_info=result)
            initial_baselines[agent_name] = f"Error: {result}" # Store error in dict
        else:
            report_progress(progress_callback, "agent_status", f"Baseline received from {agent_name}.", use_console=True)
            initial_baselines[agent_name] = result
            has_any_baseline_succeeded = True
            # Send individual baseline results to UI
            report_progress(progress_callback, "parallel_baselines", {"agent_name": agent_name, "baseline_text": result}, use_console=False)
            
    transcript_data["initial_prose_baselines"] = initial_baselines

    if not has_any_baseline_succeeded:
        msg = "Error: All agents failed to generate initial baselines. Cannot proceed."
        report_progress(progress_callback, "error", msg, use_console=True)
        return "Error: Failed initial baseline generation."

    # --- V4 Step 2: Run Free-Form Critique Round(s) --- #
    # Import the new function
    from core.debate_engine_v4 import run_freeform_critique_round
    
    critique_round_texts: Dict[str, str] = {}
    try:
        report_progress(progress_callback, "status", "Running free-form critique round (Round 1)...", use_console=True)
        critique_round_texts = await run_freeform_critique_round(
            initial_baselines=initial_baselines,
            question=question,
            progress_callback=progress_callback # Pass the callback down
        )
        # Store results in transcript
        transcript_data["debate_rounds"].append({"round": 1, "responses": critique_round_texts})
        report_progress(progress_callback, "status", "Completed free-form critique round (Round 1).", use_console=True)

    except Exception as e:
        msg = f"Error during free-form critique round: {e}"
        report_progress(progress_callback, "error", msg, use_console=True)
        logging.error("Error executing run_freeform_critique_round", exc_info=True)
        # Store partial results if any
        if critique_round_texts:
             transcript_data["debate_rounds"].append({"round": 1, "responses": critique_round_texts, "error": str(e)})
        # Decide if we should stop or proceed to synthesis with partial data?
        # For now, let's stop if the critique round fails.
        return f"Error: Failed during critique round: {e}"

    # TODO: Implement logic for subsequent debate rounds if max_rounds > 1

    # --- V4 Step 3: Synthesize Final Answer (Conditional based on synthesizer_choice) --- #
    final_synthesized_answer = "Error: Synthesis step was skipped or failed."
    
    if not transcript_data["debate_rounds"]: 
        report_progress(progress_callback, "warning", "Skipping synthesis step because debate round data is missing.", use_console=True)
    else:
        debate_texts = transcript_data["debate_rounds"] # Assuming only 1 round for now
        critique_responses = debate_texts[0].get("responses", {})
        
        if synthesizer_choice == "v3_refine":
            # --- Synthesizer 2: V3 Refinement Logic --- 
            report_progress(progress_callback, "status", "Running Synthesizer 2 (V3 Refine Style)...", use_console=True)
            reference_baseline_agent = "O4-mini" # As decided for judge
            baseline_prose = initial_baselines.get(reference_baseline_agent)

            if not baseline_prose or baseline_prose.startswith("Error:"):
                msg = f"Cannot run V3 Refine synthesizer: Reference baseline from {reference_baseline_agent} missing or failed."
                report_progress(progress_callback, "error", msg, use_console=True)
                final_synthesized_answer = f"Error: {msg}"
            else:
                # Format critique texts as a single 'debate_summary'
                debate_summary_text = ""
                for agent, text in critique_responses.items():
                    debate_summary_text += f"--- Critique from {agent} ---\n{text}\n\n"
                
                refine_prompt = REFINE_PROMPT_TEMPLATE.format(
                    question=question,
                    baseline_prose=baseline_prose,
                    debate_summary=debate_summary_text.strip()
                )
                
                try:
                    # Use a separate LLMInterface instance for refinement
                    # Could reuse synthesizer LLM config if desired
                    refine_llm = LLMInterface(model_key="gpt-o4-mini") # Or configure differently
                    report_progress(progress_callback, "status", f"Querying Refinement LLM ({refine_llm.model_name})...", use_console=False)
                    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                        task = progress.add_task("[yellow]Running V3-style refinement...", total=None)
                        # Using generate_response from LLMInterface
                        final_synthesized_answer = await asyncio.to_thread(
                            refine_llm.generate_response, 
                            prompt=refine_prompt,
                            temperature=0.5 # Consistent temp
                        )
                        progress.update(task, completed=True, visible=False)
                    report_progress(progress_callback, "status", "V3-style refinement complete.", use_console=True)
                    refine_llm.close() # Close interface if needed
                except Exception as e:
                    msg = f"Error during V3-style refinement call: {e}"
                    report_progress(progress_callback, "error", msg, use_console=True)
                    logging.error("V3 Refine Synthesizer LLM call failed", exc_info=True)
                    final_synthesized_answer = f"Error: Synthesis (V3 Refine) failed due to LLM error: {e}" 
        
        else:
            # --- Synthesizer 1: Default V4 Synthesis Logic --- 
            report_progress(progress_callback, "status", "Running Synthesizer 1 (V4 Default Style)...", use_console=True)
            try:
                final_synthesized_answer = await synthesize_final_answer(
                    question=question,
                    initial_baselines=initial_baselines,
                    debate_rounds=debate_texts, 
                    progress_callback=progress_callback
                )
                # Progress reported internally by synthesize_final_answer
            except Exception as e:
                msg = f"Error during V4 synthesis step call: {e}"
                report_progress(progress_callback, "error", msg, use_console=True)
                logging.error("Error calling synthesize_final_answer", exc_info=True)
                final_synthesized_answer = f"Error: Failed during synthesis step: {e}"

    # Store the result regardless of which synthesizer ran
    transcript_data["final_synthesized_answer"] = final_synthesized_answer
    # Report the result *before* the judge runs, so it's visible if judge fails
    report_progress(progress_callback, "synthesized_answer", final_synthesized_answer, use_console=True)
        
    # --- V4 Step 4: Judge Agent (Using V3 Strategy) --- #
    # Import the existing V3 judge function
    from judge.judge_agent import judge_quality
    
    # Select the reference baseline (e.g., O4-mini)
    reference_baseline_agent = "O4-mini" # Make configurable later if needed
    reference_baseline = initial_baselines.get(reference_baseline_agent)
    
    final_decision_answer = f"Error: Could not determine final answer. Synthesized: {final_synthesized_answer[:100]}..." # Default error
    judge_decision = "Error"
    judge_ratings = {}
    judge_raw = ""

    if not reference_baseline or reference_baseline.startswith("Error:"):
        msg = f"Reference baseline from {reference_baseline_agent} is missing or failed. Cannot run judge. Falling back to synthesized answer."
        report_progress(progress_callback, "warning", msg, use_console=True)
        judge_decision = "Skipped - No Reference Baseline"
        final_decision_answer = final_synthesized_answer # Use synthesized if no baseline to compare
        transcript_data["judge_result"] = {"decision": judge_decision, "reason": msg}
    elif final_synthesized_answer.startswith("Error:"):
        msg = f"Synthesized answer failed. Cannot run judge. Falling back to reference baseline ({reference_baseline_agent})."
        report_progress(progress_callback, "warning", msg, use_console=True)
        judge_decision = "Skipped - Synthesis Failed"
        final_decision_answer = reference_baseline # Use baseline if synthesis failed
        transcript_data["judge_result"] = {"decision": judge_decision, "reason": msg}
    else:
        # Proceed with judging
        report_progress(progress_callback, "status", f"Calling Judge Agent (comparing Synthesized vs. {reference_baseline_agent} Baseline)...", use_console=False) 
        try:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                judge_task = progress.add_task("[yellow]Calling Judge Agent...", total=None)
                judge_decision, judge_ratings, judge_raw = await judge_quality(
                    baseline_answer=reference_baseline, 
                    merged_answer=final_synthesized_answer, # Compare synthesized as the "merged" answer
                    question=question
                )
                progress.update(judge_task, completed=True, visible=False)
            report_progress(progress_callback, "status", "Judge Agent finished.", use_console=True)
            transcript_data["judge_result"] = {"decision": judge_decision, "ratings": judge_ratings, "raw_output": judge_raw}
            report_progress(progress_callback, "judge_results", transcript_data["judge_result"], use_console=True)

        except Exception as e:
            msg = f"Error calling judge: {e}"
            judge_decision = "Error"
            judge_raw = msg
            report_progress(progress_callback, "error", judge_raw, use_console=True)
            logging.error("Error executing judge_quality", exc_info=True)
            transcript_data["judge_result"] = {"decision": judge_decision, "raw_output": judge_raw}
            # Fallback on judge error - use synthesized or baseline? Let's use synthesized.
            final_decision_answer = final_synthesized_answer 
            report_progress(progress_callback, "warning", "Judge call failed, using synthesized answer as fallback.", use_console=True)

        # Determine final answer based on judge decision (only if judge ran)
        if judge_decision not in ["Skipped - No Reference Baseline", "Skipped - Synthesis Failed", "Error"]:
            if judge_decision == "Accept Merged":
                final_decision_answer = final_synthesized_answer
                report_progress(progress_callback, "final_decision", f"Accepted Synthesized (vs {reference_baseline_agent})", use_console=True)
            elif judge_decision == "Fallback to Baseline":
                final_decision_answer = reference_baseline
                report_progress(progress_callback, "final_decision", f"Fallback to {reference_baseline_agent} Baseline", use_console=True)
            else: # Error during parsing or other judge issue
                final_decision_answer = final_synthesized_answer # Fallback to synthesized if judge had parsing error
                report_progress(progress_callback, "final_decision", f"Fallback to Synthesized (Judge: {judge_decision})", use_console=True)
        
    # Ensure final_answer field in transcript is set
    transcript_data["final_decision"] = judge_decision # Store the outcome
    transcript_data["final_answer"] = final_decision_answer 
    report_progress(progress_callback, "final_answer", final_decision_answer, use_console=True)

    # --- Save Transcript --- #
    if output:
        report_progress(progress_callback, "status", f"Saving V4 transcript to {output}", use_console=False)
        try:
            with open(output, 'w') as f:
                json.dump(transcript_data, f, indent=4)
            console.print(f"\n[dim]V4 Transcript saved to {output}[/dim]")
        except Exception as e:
            msg = f"Error saving V4 transcript: {e}"
            report_progress(progress_callback, "error", msg, use_console=True)
            logging.error(f"Failed to save V4 transcript to {output}", exc_info=True)

    report_progress(progress_callback, "status", "V4 Debate complete (partial implementation).", use_console=False)
    return final_decision_answer

@app.command()
def main(
    question: str = typer.Option(None, "--question", "-q", help="The question to debate"),
    max_rounds: int = typer.Option(1, "--max-rounds", "-m", help="Maximum free-form debate rounds (V4)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    output: str = typer.Option("transcript_v4.json", "--output", "-o", help="Transcript file path (V4)")
):
    # --- Setup Logging --- 
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logger(level=log_level)
    logging.info("Starting debate application.")
    logging.debug(f"CLI Args - Question: {question}, Max Rounds: {max_rounds}, Verbose: {verbose}, Output: {output}")

    # Prompt for question if not provided
    if not question:
        question = console.input("[bold cyan]Question:[/bold cyan] ")

    console.print(f"[cyan]Question:[/cyan] {question}")
    console.print(f"[green]Max Rounds:[/green] {max_rounds}, [green]Verbose:[/green] {verbose}, [green]Output:[/green] {output}")

    # Define progress callback for CLI / Web
    # (Keep cli_progress_callback, it will ignore new V4 events initially)
    def cli_progress_callback(update_type: str, data: Any):
        if update_type == "status":
            console.print(f"[dim]STATUS: {data}[/dim]")
        elif update_type == "error" or update_type == "agent_error":
            # Handle dict-based error data from V4
            if isinstance(data, dict) and 'error' in data:
                 console.print(f"[bold red]ERROR ({data.get('agent_name', '')}): {data['error']}[/bold red]")
            else:
                console.print(f"[bold red]ERROR: {data}[/bold red]")
        # ADD Handler for parallel baselines
        elif update_type == "parallel_baselines":
            agent_name = data.get('agent_name', 'Unknown Agent')
            baseline_text = data.get('baseline_text', '[No text received]')
            console.print(f"\n--- [bold green]Baseline from {agent_name}[/bold green] ---")
            console.print(baseline_text)
            console.print(f"--- End Baseline from {agent_name} ---")
        # ADD Handler for free-form critique
        elif update_type == "freeform_critique_result":
            agent_name = data.get('agent_name', 'Unknown Agent')
            critique_text = data.get('critique_text', '[No text received]')
            console.print(f"\n--- [bold yellow]Critique from {agent_name} (Round 1)[/bold yellow] ---")
            console.print(critique_text)
            console.print(f"--- End Critique from {agent_name} ---")
        elif update_type == "synthesized_answer":
            # This might be redundant if we print the final answer after judge
            # console.print("\n[bold green]--- Synthesized Answer ---[/bold green]")
            # console.print(data)
            pass # Keep it quiet until final judge decision
        elif update_type == "judge_results":
             console.print(f"\n--- [bold purple]Judge Result[/bold purple] ---")
             console.print(data)
             console.print(f"--- End Judge Result ---")
        elif update_type == "final_decision":
            console.print(f"\n[bold cyan]Final Decision: {data}[/bold cyan]")
        # Don't print final answer here, print it after run_debate_logic returns
        # elif update_type == "final_answer":
        #     console.print("\n[bold green]--- Final Answer ---[/bold green]")
        #     console.print(data)
        # Fallback for unhandled types (optional)
        # else:
        #     console.print(f"[{update_type.upper()}] {data}")

    # Define human feedback callback for CLI
    def get_cli_human_feedback():
        console.print("\n[bold yellow]Human Feedback Requested:[/bold yellow]")
        feedback = typer.prompt("Enter feedback for the next round (or press Enter to skip)", default="", show_default=False)
        return feedback

    # Run the core debate logic
    try:
        final_answer = asyncio.run(run_debate_logic(
            question=question,
            max_rounds=max_rounds,
            output=output,
            verbose=verbose,
            progress_callback=cli_progress_callback,
            human_feedback_callback=get_cli_human_feedback,
            synthesizer_choice="v4_default"
        ))
        # UNCOMMENT: Print the final answer determined after judge logic
        console.print("\n[bold green]--- Final Answer ---[/bold green]")
        console.print(final_answer)

    except Exception as e:
        console.print(f"\n[bold red]An unexpected error occurred:[/bold red] {e}")
        logging.error("Unhandled exception in main execution", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    app() 