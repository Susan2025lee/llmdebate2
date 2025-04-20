#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import typer
import asyncio
from typing import Dict, Any
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
from core.merge_logic import merge_factors
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

async def run_debate_logic(question: str, top_k: int, max_rounds: int, output: str, verbose: bool):
    """Core async logic for running the debate baseline and rounds."""
    console.print(f"[bold magenta]Running debate for:[/bold magenta] {question}")

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
    console.print(f"[bold cyan]Anchor Agent for V2:[/bold cyan] {anchor_agent_name}")

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
        console.print(f"[bold red]Error:[/bold red] Anchor agent '{anchor_agent_name}' not found in available clients. Exiting.")
        sys.exit(1)
    
    anchor_query_func = agent_query_functions[anchor_agent_name]
    prose_baseline_prompt = PROSE_BASELINE_GENERATION_TEMPLATE.format(question=question)
    transcript_data["baseline_prompt"] = prose_baseline_prompt # Store the prompt used

    prose_baseline = "Error: Failed to generate prose baseline."
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        baseline_task = progress.add_task(f"[yellow]Querying Anchor Agent ({anchor_agent_name}) for prose baseline...", total=None)
        try:
            prose_baseline = await anchor_query_func(prose_baseline_prompt)
            transcript_data["initial_prose_baseline"] = prose_baseline
            console.print(f"\n[bold green]Initial Prose Baseline from {anchor_agent_name}:[/bold green]")
            console.print(prose_baseline)
        except Exception as e:
            console.print(f"\n[bold red]Error generating prose baseline from {anchor_agent_name}: {e}[/bold red]")
            logging.error(f"Failed to generate prose baseline", exc_info=True)
            transcript_data["initial_prose_baseline"] = f"Error: {e}"
            # Decide if we should exit or try to continue without a baseline? Exit for now.
            sys.exit(1)
        finally:
            progress.update(baseline_task, completed=True, visible=False)


    # --- V2: Step 2 - Initiate Critique & Factor Generation (Round 1 Seed) --- #
    critique_tasks = []
    critique_prompts = {}
    agent_names = list(agent_query_functions.keys())

    console.print(f"\n[yellow]Generating initial factors via critique of prose baseline...[/yellow]")
    for name in agent_names:
        critique_prompt = CRITIQUE_PROSE_BASELINE_TEMPLATE.format(
            question=question,
            prose_baseline=prose_baseline
        )
        critique_prompts[name] = critique_prompt # Store for logging/debug if needed
        # logger.debug(f"Critique prompt for {name}:\n{critique_prompt[:500]}...")
        query_func = agent_query_functions[name]
        critique_tasks.append(query_func(critique_prompt))
    
    # Use Rich Progress for async tasks
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        critique_task = progress.add_task("[yellow]Querying agents for baseline critique/factors...", total=None)
        critique_results = await asyncio.gather(*critique_tasks, return_exceptions=True)
        progress.update(critique_task, completed=True, visible=False)

    # Process critique results to seed the debate
    initial_responses: Dict[str, AgentResponse] = {}
    transcript_data["baseline_responses"] = [] # Reuse this field for the critique round outputs
    console.print("\n[bold yellow][Critique Round Results (Seeding Debate)][/bold yellow]")
    for name, resp in zip(agent_names, critique_results):
        agent_resp_obj = AgentResponse(agent_name=name)
        # Store critique round output similar to how baseline was stored before
        resp_data = {"agent_name": name, "raw_response": None, "error": None, "factors": [], "prompt_used": critique_prompts[name]}
        if isinstance(resp, Exception):
            console.print(f"[[bold red]{name}[/bold red]] [red]Error during critique: {resp}[/red]")
            agent_resp_obj.raw_response = f"Error: {resp}"
            resp_data["error"] = str(resp)
        else:
            console.print(f"[[bold blue]{name}[/bold blue]] Critique/Factors Response Received.")
            agent_resp_obj.raw_response = resp 
            resp_data["raw_response"] = resp
            # Parse the JSON factor list from the critique response
            parsed_factors = _parse_factor_list(resp)
            agent_resp_obj.factors = parsed_factors
            resp_data["factors"] = [f.__dict__ for f in parsed_factors]
            console.print(f"[[bold blue]{name}[/bold blue]] Parsed Factors from Critique: {len(parsed_factors)} factors")

        initial_responses[name] = agent_resp_obj
        transcript_data["baseline_responses"].append(resp_data)

    # Check if any agent successfully produced factors
    if not any(resp.factors for resp in initial_responses.values()):
        console.print("[bold red]Error: No agents successfully produced factors from the critique round. Cannot proceed with debate.[/bold red]")
        sys.exit(1)
        
    # --- Run Debate Rounds (Starts from effective Round 2) --- #
    def get_human_feedback():
        # Use Console input which integrates better with Rich displays
        return console.input("[bold yellow]Press Enter to continue or type feedback:[/bold yellow] ")

    debate_history_obj = await run_debate_rounds(
        initial_responses=initial_responses,
        question=question,
        max_rounds=max_rounds,
        human_feedback_callback=get_human_feedback # Pass the callback
    )

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
    merged_factors = [] # Ensure variable exists
    if debate_history_obj:
        final_agent_responses = debate_history_obj[-1]
        console.print("\n[yellow]Merging final factors...[/yellow]")
        merged_factors = merge_factors(
            final_responses=final_agent_responses,
            top_k=top_k # Pass the CLI arg
            # min_endorsements and min_confidence use defaults
        )
        console.print("\n[bold yellow][Merged Factors][/bold yellow]")
        if merged_factors:
            for factor in merged_factors:
                endorsements = getattr(factor, 'endorsement_count', 'N/A')
                console.print(f"- [bold magenta]{factor.name}[/bold magenta] (Endorsements: {endorsements}, Mean Confidence: {factor.confidence:.2f})")
            # Store merged factors in transcript (Factor objects to dicts)
            transcript_data["merged_factors"] = [f.__dict__ for f in merged_factors]
        else:
            console.print("[red]No factors met the merge criteria.[/red]")
    else:
        console.print("\n[bold red]Error:[/bold red] Debate history is empty, cannot merge.")
        # merged_factors already initialized

    # --- Generate Summary --- #
    final_summary = "Summary could not be generated."
    if merged_factors:
        # Add spinner for summary generation
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
            summary_task = progress.add_task("[yellow]Generating final summary...", total=None)
            final_summary = await generate_summary(merged_factors)
            progress.update(summary_task, completed=True, visible=False)

        transcript_data["final_summary"] = final_summary
        console.print("\n[bold green][Final Summary][/bold green]")
        console.print(final_summary)
    else:
        console.print("\n[yellow]Skipping summary generation as no factors were merged.[/yellow]")
        transcript_data["final_summary"] = "Skipped - no merged factors."

    # --- Judge Agent --- #
    # Add spinner for judge agent
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        judge_task = progress.add_task("[yellow]Calling Judge Agent...", total=None)
        judge_decision, judge_ratings, judge_raw = await judge_quality(
            baseline_answer=prose_baseline, # <-- Use the initial anchor agent prose baseline
            merged_answer=final_summary,
            question=question
        )
        progress.update(judge_task, completed=True, visible=False)

    # --- Final Output Selection --- #
    console.print("\n[bold yellow][Final Answer Selection][/bold yellow]")
    if judge_decision == "Accept Merged":
        console.print("[green]Judge approved merged answer.[/green]")
        final_output = final_summary
        transcript_data["final_decision"] = "Accepted Merged"
    elif judge_decision == "Fallback to Baseline":
        console.print("[red]Judge recommended fallback to baseline.[/red]")
        final_output = prose_baseline # <-- Use the initial anchor agent prose baseline on fallback
        transcript_data["final_decision"] = "Fell back to Baseline"
    else: # Error case
        console.print(f"[bold red]Judge resulted in error:[/bold red] {judge_decision}. Defaulting to merged answer.")
        final_output = final_summary
        transcript_data["final_decision"] = f"Error ({judge_decision}) - Used Merged"

    transcript_data["final_answer"] = final_output

    console.print("\n[bold cyan]=== FINAL ANSWER ===[/bold cyan]")
    console.print(final_output)

    # --- Write Transcript --- 
    try:
        with open(output, 'w') as f:
            json.dump(transcript_data, f, indent=4)
        console.print(f"\n[green]Transcript saved to {output}[/green]")
        logging.info(f"Transcript successfully saved to {output}")
    except Exception as e:
        console.print(f"\n[bold red]Error saving transcript to {output}:[/bold red] {e}")
        logging.error(f"Failed to save transcript to {output}", exc_info=True)

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

    # Run the core async logic
    asyncio.run(run_debate_logic(question, top_k, max_rounds, output, verbose))

if __name__ == "__main__":
    app() 