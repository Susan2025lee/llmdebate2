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
# from llm_interface import LLMInterface

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
    CRITIQUE_PROSE_BASELINE_TEMPLATE
)

# Initialize Rich Console
console = Console()

app = typer.Typer()

# Helper to safely call the callback or print to console
def report_progress(callback: Optional[Callable[[str, Any], None]], update_type: str, data: Any, use_console: bool = True):
    if callback:
        try:
            callback(update_type, data)
        except Exception as e:
            # Log callback error but continue
            logging.error(f"Error in progress callback: {e}", exc_info=True)
            # Fallback to console if callback fails?
            if use_console:
                console.print(f"[Callback Error] [{update_type.upper()}] {data}") 
    elif use_console:
        # Default console printing if no callback
        # Simple printing for now, can enhance later if needed
        console.print(f"[{update_type.upper()}] {data}")

async def run_debate_logic(
    question: str, 
    top_k: int, 
    max_rounds: int, 
    output: Optional[str], # Allow None for web use
    verbose: bool, 
    progress_callback: Optional[Callable[[str, Any], None]] = None, # New callback
    human_feedback_callback: Optional[Callable[[], str]] = None # Existing callback, ensure Optional
):
    """Core async logic for running the debate, reporting progress via callback."""
    report_progress(progress_callback, "status", f"Starting debate for: {question}", use_console=True) # Keep initial console print

    # --- Transcript Data --- 
    transcript_data: Dict[str, Any] = {
        "question": question,
        "parameters": {
            "max_rounds": max_rounds,
            "top_k": top_k,
            "verbose": verbose,
            "output_file": output
        },
        "baseline_prompt": "",
        "baseline_responses": [], # List of AgentResponse-like dicts
        "debate_history": [], # List of round dicts, each mapping agent_name to AgentResponse-like dict
        "merged_factors": [], # List of Factor-like dicts
        "final_summary": "",
        "judge_result": {},
        "final_decision": "",
        "final_answer": "",
        "baseline_prose_summary": "",
        "anchor_agent": "", # Track which agent was the anchor
        "initial_prose_baseline": "" # Store the raw prose baseline
    }

    # --- V2: Determine Anchor Agent --- 
    anchor_agent_name = os.getenv("ANCHOR_AGENT_NAME", "O4-mini") # Default to O4-mini
    transcript_data["anchor_agent"] = anchor_agent_name
    report_progress(progress_callback, "status", f"Anchor Agent for V2: {anchor_agent_name}", use_console=True)

    # --- V2: Step 1 - Generate High-Quality Prose Baseline --- 
    from llm_clients.o4_client import query_o4
    from llm_clients.gemini_client import query_gemini
    # Map agent names to their query functions
    # TODO: Consider moving this mapping to a shared utility or config
    agent_query_functions = {
        "O4-mini": query_o4,
        "Gemini-2.5": query_gemini
    }
    try:
        from llm_clients.grok_client import query_grok # type: ignore
        agent_query_functions["Grok-3"] = query_grok
    except ImportError:
        pass # Grok is optional

    if anchor_agent_name not in agent_query_functions:
        msg = f"Error: Anchor agent '{anchor_agent_name}' not found. Exiting."
        report_progress(progress_callback, "error", msg, use_console=True)
        # Decide how to handle exit for web? Raise exception? Return error status?
        # For now, print and rely on caller (Flask) to handle potential downstream issues or lack of data.
        # Consider raising a specific exception for web context later.
        return "Error: Anchor agent configuration issue." # Return error string
    
    anchor_query_func = agent_query_functions[anchor_agent_name]
    prose_baseline_prompt = PROSE_BASELINE_GENERATION_TEMPLATE.format(question=question)
    transcript_data["baseline_prompt"] = prose_baseline_prompt

    prose_baseline = "Error: Failed to generate prose baseline."
    report_progress(progress_callback, "status", f"Querying Anchor Agent ({anchor_agent_name}) for prose baseline...", use_console=False) # Handled by progress bar
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        baseline_task = progress.add_task(f"[yellow]Querying Anchor Agent ({anchor_agent_name})...", total=None)
        try:
            prose_baseline = await anchor_query_func(prose_baseline_prompt)
            transcript_data["initial_prose_baseline"] = prose_baseline
            report_progress(progress_callback, "status", f"Initial Prose Baseline received from {anchor_agent_name}.", use_console=True)
            report_progress(progress_callback, "baseline_result", prose_baseline, use_console=True)
        except Exception as e:
            msg = f"Error generating prose baseline from {anchor_agent_name}: {e}"
            report_progress(progress_callback, "error", msg, use_console=True)
            logging.error(f"Failed to generate prose baseline", exc_info=True)
            transcript_data["initial_prose_baseline"] = f"Error: {e}"
            # Again, consider raising exception for web
            return f"Error: Failed to generate baseline: {e}" # Return specific error
        finally:
            progress.update(baseline_task, completed=True, visible=False)


    # --- V2: Step 2 - Initiate Critique & Factor Generation (Round 1 Seed) --- #
    critique_tasks = []
    critique_prompts = {}
    agent_names = list(agent_query_functions.keys())

    report_progress(progress_callback, "status", "Generating initial factors via critique of prose baseline...", use_console=True)
    for name in agent_names:
        critique_prompt = CRITIQUE_PROSE_BASELINE_TEMPLATE.format(
            question=question,
            prose_baseline=prose_baseline
        )
        critique_prompts[name] = critique_prompt # Store for logging/debug if needed
        # logger.debug(f"Critique prompt for {name}:\n{critique_prompt[:500]}...")
        query_func = agent_query_functions[name]
        critique_tasks.append(query_func(critique_prompt))
    
    report_progress(progress_callback, "status", "Querying agents for baseline critique/factors...", use_console=False) # Handled by progress bar
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        critique_task = progress.add_task("[yellow]Querying agents for critique...", total=None)
        critique_results = await asyncio.gather(*critique_tasks, return_exceptions=True)
        progress.update(critique_task, completed=True, visible=False)

    # Process critique results to seed the debate
    initial_responses: Dict[str, AgentResponse] = {}
    transcript_data["baseline_responses"] = [] # Reuse this field for the critique round outputs
    report_progress(progress_callback, "status", "Processing critique round results...", use_console=True)
    critique_round_data = {}
    for name, resp in zip(agent_names, critique_results):
        agent_resp_obj = AgentResponse(agent_name=name)
        # Store critique round output similar to how baseline was stored before
        resp_data = {"agent_name": name, "raw_response": None, "error": None, "factors": [], "prompt_used": critique_prompts[name]}
        if isinstance(resp, Exception):
            msg = f"{name}: Error during critique: {resp}"
            report_progress(progress_callback, "agent_error", msg, use_console=True)
            agent_resp_obj.raw_response = f"Error: {resp}"
            resp_data["error"] = str(resp)
        else:
            report_progress(progress_callback, "agent_status", f"{name}: Critique/Factors Response Received.", use_console=True)
            agent_resp_obj.raw_response = resp 
            resp_data["raw_response"] = resp
            # Parse the JSON factor list from the critique response
            parsed_factors = _parse_factor_list(resp)
            agent_resp_obj.factors = parsed_factors
            resp_data["factors"] = [f.__dict__ for f in parsed_factors]
            report_progress(progress_callback, "agent_result", {"name": name, "factors": [f.__dict__ for f in agent_resp_obj.factors]}, use_console=True)

        initial_responses[name] = agent_resp_obj
        transcript_data["baseline_responses"].append(resp_data)
        critique_round_data[name] = resp_data # For callback
    
    report_progress(progress_callback, "critique_complete", critique_round_data, use_console=False) # Send structured critique data

    if not any(resp.factors for resp in initial_responses.values()):
        msg = "Error: No agents successfully produced factors from the critique round. Cannot proceed."
        report_progress(progress_callback, "error", msg, use_console=True)
        return "Error: Failed critique round."
        
    # --- Run Debate Rounds (Starts from effective Round 2) --- #
    report_progress(progress_callback, "status", "Starting debate rounds...", use_console=True)
    
    # Call run_debate_rounds with the PASSED-IN human_feedback_callback
    debate_history_obj = []
    try:
        debate_history_obj = await run_debate_rounds(
            initial_responses=initial_responses,
            question=question,
            max_rounds=max_rounds,
            human_feedback_callback=human_feedback_callback # Use the callback passed as argument
        )
        report_progress(progress_callback, "status", "Debate rounds complete.", use_console=True)
    except Exception as e:
        msg = f"Error during debate rounds: {e}"
        report_progress(progress_callback, "error", msg, use_console=True)
        logging.error("Error executing run_debate_rounds", exc_info=True)
        # Include round history in transcript even if rounds failed mid-way
        # if 'debate_history' in transcript_data and debate_history_obj: # Check if it was partially populated
        #     # transcript_data["debate_history"] = [ ... ] # Removed incomplete line
        #     pass # Placeholder if we want to re-add serialization later
        return f"Error: Failed during debate rounds: {e}"

    # Convert debate history objects to serializable dicts
    transcript_data["debate_history"] = [
        {an: {
                "agent_name": ar.agent_name,
                "factors": [f.__dict__ for f in ar.factors], # Convert Factors
                "critique": ar.critique,
                "raw_response": ar.raw_response
            } for an, ar in round_responses.items()} 
        for round_responses in debate_history_obj # debate_history_obj includes initial
    ]

    # --- Merge Factors --- #
    merged_factors = [] # Initialize
    if debate_history_obj:
        final_agent_responses = debate_history_obj[-1]
        report_progress(progress_callback, "status", "Merging final factors...", use_console=True)
        # The merge_factors function is now async and handles its own console output
        try:
            merged_factors = await merge_factors(
                final_responses=final_agent_responses,
                question=question,
                top_k=top_k # Pass the CLI arg
            )
            # Store merged factors in transcript (Factor objects to dicts)
            if merged_factors:
                transcript_data["merged_factors"] = [f.__dict__ for f in merged_factors]
                report_progress(progress_callback, "merge_result", transcript_data["merged_factors"], use_console=True)
            else:
                # Handle case where merge returns empty (e.g., LLM error)
                transcript_data["merged_factors"] = [] 
                report_progress(progress_callback, "warning", "Factor merging resulted in no factors.", use_console=True)
        except Exception as e:
            msg = f"Error during factor merging: {e}"
            report_progress(progress_callback, "error", msg, use_console=True)
            logging.error("Error executing merge_factors", exc_info=True)
            transcript_data["merged_factors"] = [] # Ensure empty on error
            # Decide whether to stop or continue without merge? Continue for now.
            # return f"Error: Failed during factor merging: {e}" # Option to stop
    else:
        report_progress(progress_callback, "error", "Debate history empty, cannot merge.", use_console=True)
        # merged_factors already initialized to []
        transcript_data["merged_factors"] = []

    # --- Generate Summary --- #
    final_summary = "Summary could not be generated."
    if merged_factors:
        report_progress(progress_callback, "status", "Generating final summary...", use_console=False) # Uses progress bar
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
            summary_task = progress.add_task("[yellow]Generating summary...", total=None)
            try:
                final_summary = await generate_summary(merged_factors)
                report_progress(progress_callback, "status", "Final summary generated.", use_console=True)
                report_progress(progress_callback, "summary_result", final_summary, use_console=True)
            except Exception as e:
                 final_summary = f"Error generating summary: {e}" # Update summary on error
                 report_progress(progress_callback, "error", final_summary, use_console=True)
                 logging.error("Error executing generate_summary", exc_info=True)
            finally:
                 progress.update(summary_task, completed=True, visible=False)
        transcript_data["final_summary"] = final_summary
        report_progress(progress_callback, "status", "Final summary generated.", use_console=True)
        report_progress(progress_callback, "summary_result", final_summary, use_console=True)
    else:
        report_progress(progress_callback, "status", "Skipping summary generation as no factors were merged.", use_console=True)
        transcript_data["final_summary"] = "Skipped - no merged factors."

    # --- V3: Refine Baseline with Debate Summary --- #
    refined_answer = "Refinement step skipped or failed."
    if final_summary != "Skipped - no merged factors." and final_summary != "Summary could not be generated.":
        report_progress(progress_callback, "status", "Integrating debate insights into baseline...", use_console=False) # Uses progress bar
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
            refine_task = progress.add_task("[yellow]Refining baseline...", total=None)
            try:
                refined_answer = await refine_with_debate_summary(
                    baseline_prose=prose_baseline,
                    debate_summary=final_summary,
                    question=question
                )
                report_progress(progress_callback, "status", "Refinement complete.", use_console=True)
                report_progress(progress_callback, "refine_result", refined_answer, use_console=True)
            except Exception as e:
                refined_answer = f"Error during refinement: {e}" # Update answer on error
                report_progress(progress_callback, "error", refined_answer, use_console=True)
                logging.error("Error executing refine_with_debate_summary", exc_info=True)
            finally:
                progress.update(refine_task, completed=True, visible=False)
        transcript_data["refined_answer"] = refined_answer # Log the refined answer
        report_progress(progress_callback, "status", "Refined answer generated.", use_console=True)
        report_progress(progress_callback, "refine_result", refined_answer, use_console=True)
    else:
        # If summary failed or was skipped, refinement doesn't make sense.
        # Use baseline as the candidate for the judge instead.
        report_progress(progress_callback, "status", "Skipping refinement step as debate summary was not generated.", use_console=True)
        refined_answer = prose_baseline # Judge will compare baseline vs baseline
        transcript_data["refined_answer"] = "Skipped - no debate summary."


    # --- Judge Agent --- #
    final_decision_answer = "Error: Judge did not provide a final answer." # Default
    report_progress(progress_callback, "status", "Calling Judge Agent...", use_console=False) # Uses progress bar
    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
            judge_task = progress.add_task("[yellow]Calling Judge Agent...", total=None)
            # Judge now compares baseline vs the *refined* answer
            judge_decision, judge_ratings, judge_raw = await judge_quality(
                baseline_answer=prose_baseline, 
                merged_answer=refined_answer, # <-- Pass refined_answer
                question=question
            )
            report_progress(progress_callback, "status", "Judge Agent finished.", use_console=True)
    except Exception as e: # Catch errors related to Progress bar itself if any
        judge_decision = "Error"
        judge_raw = f"Error calling judge: {e}"
        report_progress(progress_callback, "error", judge_raw, use_console=True)
        logging.error("Error executing judge_quality", exc_info=True)

    # --- Final Decision --- #
    transcript_data["judge_result"] = {"decision": judge_decision, "ratings": judge_ratings, "raw_output": judge_raw}
    report_progress(progress_callback, "judge_result", transcript_data["judge_result"], use_console=True) # Send structured judge data

    if judge_decision == "Merged":
        final_decision_answer = refined_answer
        report_progress(progress_callback, "final_decision", "Accepted Refined", use_console=True)
    elif judge_decision == "Baseline":
        final_decision_answer = prose_baseline
        report_progress(progress_callback, "final_decision", "Accepted Baseline", use_console=True)
    else: # Error or fallback
        final_decision_answer = refined_answer # Fallback to refined if judge fails
        report_progress(progress_callback, "final_decision", f"Fallback to Refined (Judge: {judge_decision})", use_console=True)
    
    report_progress(progress_callback, "final_answer", final_decision_answer, use_console=True) # Send final answer
    
    transcript_data["final_decision"] = judge_decision
    transcript_data["final_answer"] = final_decision_answer # Store in transcript

    # --- Save Transcript --- #
    if output:
        report_progress(progress_callback, "status", f"Saving transcript to {output}", use_console=False) # Keep console print for dim
        try:
            with open(output, 'w') as f:
                json.dump(transcript_data, f, indent=4)
            console.print(f"\n[dim]Transcript saved to {output}[/dim]") # Keep confirmation on console
        except Exception as e:
            msg = f"Error saving transcript: {e}"
            report_progress(progress_callback, "error", msg, use_console=True)
            logging.error(f"Failed to save transcript to {output}", exc_info=True)

    report_progress(progress_callback, "status", "Debate complete.", use_console=False)
    return final_decision_answer

@app.command()
def main(
    question: str = typer.Option(None, "--question", "-q", help="The question to debate"),
    max_rounds: int = typer.Option(3, "--max-rounds", "-m", help="Maximum debate rounds"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Top K factors to merge"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    output: str = typer.Option("transcript.json", "--output", "-o", help="Transcript file path")
):
    """
    CLI entrypoint for the multi-LLM debate system.
    """
    # --- Setup Logging --- 
    log_level = logging.DEBUG if verbose else logging.INFO
    setup_logger(level=log_level)
    logging.info("Starting debate application.")
    logging.debug(f"CLI Args - Question: {question}, Max Rounds: {max_rounds}, Top K: {top_k}, Verbose: {verbose}, Output: {output}")

    # Prompt for question if not provided
    if not question:
        question = console.input("[bold cyan]Question:[/bold cyan] ")

    console.print(f"[cyan]Question:[/cyan] {question}")
    console.print(f"[green]Max Rounds:[/green] {max_rounds}, [green]Top K:[/green] {top_k}, [green]Verbose:[/green] {verbose}, [green]Output:[/green] {output}")

    # Initialize LLM interface with default or env-specified model
    # We don't need the instance directly here anymore if clients handle their own
    # llm = LLMInterface()

    # Define the CLI progress callback
    def cli_progress_callback(update_type: str, data: Any):
        # Simple console printing, mimicking previous behavior
        # Can be made more sophisticated with Rich formatting based on type
        if update_type == "status" or update_type == "agent_status" or update_type == "final_decision":
            console.print(f"[cyan]{data}[/cyan]")
        elif update_type == "error" or update_type == "agent_error":
            console.print(f"[bold red]{data}[/bold red]")
        elif update_type == "warning":
             console.print(f"[yellow]{data}[/yellow]")
        elif update_type == "baseline_result" or update_type == "summary_result" or update_type == "refine_result":
             console.print(f"\n[bold green][{update_type.replace('_result', '').upper()}][/bold green]")
             console.print(data)
        elif update_type == "agent_result":
            console.print(f"[[bold blue]{data['name']}[/bold blue]] Parsed Factors: {len(data['factors'])} factors")
        elif update_type == "merge_result":
            console.print(f"\n[bold green][MERGE RESULT][/bold green]")
            # Print factors nicely?
            console.print(f"{len(data)} factors merged.") 
        elif update_type == "judge_result":
            console.print("\n[bold green][Judge Decision][/bold green]")
            console.print(f"Judge chose: {data['decision']}")
            ratings = data.get('ratings')
            if isinstance(ratings, dict) and 'baseline' in ratings and 'merged' in ratings:
                 console.print(f"Ratings: Baseline={ratings['baseline']}, Merged={ratings['merged']}")
            elif ratings:
                 console.print(f"[yellow]Note: Judge ratings received incomplete: {ratings}[/yellow]")
        elif update_type == "final_answer":
             console.print(f"\n[bold magenta]=== FINAL ANSWER ===[/bold magenta]")
             console.print(data)
        # else: # Ignore other types like critique_complete for CLI?
        #     console.print(f"[{update_type.upper()}] {str(data)[:200]}...") # Generic fallback

    # Define the CLI *specific* feedback callback HERE
    def get_cli_human_feedback():
        return console.input("[bold yellow]Press Enter to continue or type feedback:[/bold yellow] ")

    # Run the core async logic, passing the CLI callbacks
    final_answer = asyncio.run(run_debate_logic(
        question=question,
        top_k=top_k,
        max_rounds=max_rounds,
        output=output,
        verbose=verbose,
        progress_callback=cli_progress_callback, 
        human_feedback_callback=get_cli_human_feedback # Pass the function defined above
    ))

    # Final answer is already printed by the callback
    # console.print("\n[bold magenta]--- Debate Complete ---[/bold magenta]")

if __name__ == "__main__":
    app() 