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
from utils.prompts import BASELINE_PROMPT_TEMPLATE

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
        "baseline_prose_summary": ""
    }

    # --- Baseline & Fan-Out ---
    from llm_clients.o4_client import query_o4
    from llm_clients.gemini_client import query_gemini
    # Optional Grok client if available
    try:
        from llm_clients.grok_client import query_grok # type: ignore
        has_grok = True
    except ImportError:
        has_grok = False

    # Build baseline prompt
    baseline_prompt = BASELINE_PROMPT_TEMPLATE.format(question=question, top_k=top_k)
    transcript_data["baseline_prompt"] = baseline_prompt
    console.print(f"\n[cyan]Baseline prompt:[/cyan]\n{baseline_prompt}") # Debug print

    # Query each agent in parallel
    tasks = [query_o4(baseline_prompt), query_gemini(baseline_prompt)]
    agent_names = ["O4-mini", "Gemini-2.5"]
    if has_grok:
        tasks.append(query_grok(baseline_prompt))
        agent_names.append("Grok-3")

    # Use Rich Progress for async tasks
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True # Hide progress bar when done
    ) as progress:
        baseline_task = progress.add_task("[yellow]Querying baseline models...", total=None)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        progress.update(baseline_task, completed=True, visible=False) # Hide task when done

    # Process and log baseline results 
    initial_responses: Dict[str, AgentResponse] = {}
    baseline_answer_for_judge = "Error: Could not get baseline answer."
    console.print("\n[bold yellow][Baseline Results][/bold yellow]")
    for name, resp in zip(agent_names, results):
        agent_resp_obj = AgentResponse(agent_name=name)
        resp_data = {"agent_name": name, "raw_response": None, "error": None, "factors": []}
        if isinstance(resp, Exception):
            console.print(f"[[bold red]{name}[/bold red]] [red]Error: {resp}[/red]")
            agent_resp_obj.raw_response = f"Error: {resp}"
            resp_data["error"] = str(resp)
        else:
            console.print(f"[[bold blue]{name}[/bold blue]] Response Received.")
            agent_resp_obj.raw_response = resp 
            resp_data["raw_response"] = resp
            # Now parse the baseline response using the same parser
            parsed_baseline_factors = _parse_factor_list(resp)
            agent_resp_obj.factors = parsed_baseline_factors # Store actual Factor objects
            resp_data["factors"] = [f.__dict__ for f in parsed_baseline_factors] # Store dicts in transcript
            console.print(f"[[bold blue]{name}[/bold blue]] Parsed Factors: {len(parsed_baseline_factors)} factors")
            # console.print(f"[[bold blue]{name}[/bold blue]] Raw: {resp[:100]}...") # Optionally hide raw if parsed ok

            # Store the first successful response as baseline for judge
            if name == agent_names[0] and baseline_answer_for_judge.startswith("Error:"):
                baseline_answer_for_judge = resp # Store the raw JSON string

        initial_responses[name] = agent_resp_obj
        transcript_data["baseline_responses"].append(resp_data)
        
    # --- Run Debate Rounds --- #
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

    # --- Generate Baseline Summary (for Judge and potential Fallback) --- #
    baseline_prose_summary = "Baseline summary could not be generated."
    try:
        baseline_factors_for_summary = _parse_factor_list(baseline_answer_for_judge)
        if baseline_factors_for_summary:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
                summary_task = progress.add_task("[yellow]Generating baseline summary...", total=None)
                baseline_prose_summary = await generate_summary(baseline_factors_for_summary)
                progress.update(summary_task, completed=True, visible=False)
            transcript_data["baseline_prose_summary"] = baseline_prose_summary # Store in transcript
        else:
            logging.warning("Could not parse baseline factors to generate its summary.")
            transcript_data["baseline_prose_summary"] = "Error: Could not parse baseline factors."
    except Exception as e:
        logging.error(f"Error generating baseline summary: {e}", exc_info=True)
        baseline_prose_summary = f"Error generating baseline summary: {e}"
        transcript_data["baseline_prose_summary"] = baseline_prose_summary

    # --- Judge Agent --- #
    # Add spinner for judge agent
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console, transient=True) as progress:
        judge_task = progress.add_task("[yellow]Calling Judge Agent...", total=None)
        judge_decision, judge_ratings, judge_raw = await judge_quality(
            baseline_answer=baseline_prose_summary, # Use the generated prose summary
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
        final_output = baseline_prose_summary # Use the generated baseline prose summary
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