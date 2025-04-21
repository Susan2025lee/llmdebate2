import asyncio
import re
from typing import Dict, Tuple
import logging

from utils.prompts import JUDGE_PROMPT_TEMPLATE, JUDGE_V4_PROMPT_TEMPLATE
# Use the default O4 client for judging for now
from llm_clients.o4_client import query_o4
from rich.console import Console # Use Rich for printing

JudgeRatings = Dict[str, str] # e.g., {"Completeness": "Better", "Correctness": "Equal", ...}
JudgeDecision = str # e.g., "Accept Merged", "Fallback to Baseline"

# Setup logger for this module
logger = logging.getLogger(__name__)
# Initialize Rich Console (or import)
console = Console()

def _parse_judge_ratings(text: str) -> JudgeRatings:
    """Parses the raw LLM judge output into a dictionary of ratings."""
    ratings = {}
    # More flexible regex to handle variations like numbering and rating placement
    pattern = r"^\s*(?:\d+\.\s*)?(Completeness|Correctness|Clarity):\s*(?:Rating:\s*\[?)?(Better|Worse|Equal)\]?"
    # Explanation:
    # ^\s*             -> Start of line, optional whitespace
    # (?:\d+\.\s*)?    -> Optional numbering (e.g., "1. ")
    # (Completeness|...) -> Capture dimension name
    # :\s*             -> Colon and optional whitespace
    # (?:Rating:\s*\[?)? -> Optional "Rating: [" part
    # (Better|Worse|Equal) -> Capture the rating
    # \]?               -> Optional closing bracket
    
    matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
    
    expected_dimensions = {"Completeness", "Correctness", "Clarity"}
    found_dimensions = set()
    
    for match in matches:
        dimension, rating = match
        dimension_normalized = dimension.capitalize()
        if dimension_normalized in expected_dimensions:
            ratings[dimension_normalized] = rating.capitalize()
            found_dimensions.add(dimension_normalized)
            
    # Check if all expected dimensions were found
    if found_dimensions != expected_dimensions:
        logger.warning(f"Judge response missing dimensions. Found: {found_dimensions}. Response: {text[:300]}...")
        # Fill missing with a default or handle error? Let's default to 'Equal' for now
        for dim in expected_dimensions - found_dimensions:
            ratings[dim] = "Equal" 
            
    return ratings

async def judge_quality(
    baseline_answer: str, 
    merged_answer: str, 
    question: str
) -> Tuple[JudgeDecision, JudgeRatings, str]:
    """
    Uses an LLM to compare the baseline and merged answers and decide which is better.

    Args:
        baseline_answer: The initial answer from the baseline model.
        merged_answer: The final answer produced after the debate and merge steps.
        question: The original user question.

    Returns:
        A tuple containing:
        - decision (JudgeDecision): "Accept Merged" or "Fallback to Baseline".
        - ratings (JudgeRatings): Dictionary of ratings per dimension.
        - raw_judge_response (str): The raw text output from the judge LLM.
    """
    if not baseline_answer or not merged_answer:
        return "Error", {}, "Missing baseline or merged answer for judging."
        
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        question=question,
        baseline_answer=baseline_answer,
        merged_answer=merged_answer
    )
    
    # --- Added Print Statements ---
    console.print("\n--- [bold purple]Baseline Factors Sent to Judge[/bold purple] ---")
    console.print(baseline_answer)
    console.print("--- End Baseline Factors for Judge ---")
    console.print("\n--- [bold purple]Debate Factors Sent to Judge[/bold purple] ---")
    console.print(merged_answer)
    console.print("--- End Debate Factors for Judge ---")
    # --- End Added Print Statements ---

    logger.info("Calling Judge Agent...")
    # logger.debug(f"Judge Prompt:\n{prompt[:500]}...")

    raw_judge_response = "Error: Judge LLM query failed."
    ratings = {dim: "Error" for dim in ["Completeness", "Correctness", "Clarity"]}
    decision: JudgeDecision = "Error"
    
    try:
        raw_judge_response = await query_o4(prompt)
        logger.debug(f"Judge Agent Raw Response:\n{raw_judge_response}")
        # Keep console print for user visibility
        console.print("[bold white][Judge Agent Raw Response][/bold white]")
        console.print(raw_judge_response)
        
        ratings = _parse_judge_ratings(raw_judge_response)
        logger.info(f"Judge Agent Parsed Ratings: {ratings}")
        # Keep console print for user visibility
        console.print(f"[bold cyan][Judge Agent Parsed Ratings]:[/bold cyan] {ratings}")

        # Determine final decision
        if any(rating == "Worse" for rating in ratings.values()):
            decision = "Fallback to Baseline"
            logger.info("Judge Decision: Fallback to Baseline (found 'Worse' rating)")
            # Keep console print
            console.print("[red]Judge Decision: Fallback to Baseline (found 'Worse' rating)[/red]")
        elif "Error" in ratings.values():
             decision = "Error during parsing"
             logger.warning(f"Judge Decision: Error during parsing. Ratings: {ratings}")
             # Keep console print
             console.print("[red]Judge Decision: Error during parsing[/red]")
        else:
            decision = "Accept Merged"
            logger.info("Judge Decision: Accept Merged")
            # Keep console print
            console.print("[green]Judge Decision: Accept Merged[/green]")
            
    except Exception as e:
        logger.error("Error during judge query.", exc_info=True)
        raw_judge_response = f"Error: Failed to get judge response. {e}"
        decision = "Error"
        
    # --- Added Print Statement ---
    console.print("\n--- [bold purple]Parsed Judge Ratings[/bold purple] ---")
    console.print(ratings)
    console.print("--- End Parsed Judge Ratings ---\n")
    # --- End Added Print Statement ---

    return decision, ratings, raw_judge_response

# Example (for testing structure)
# async def main_test():
#     q = "What is the best language?"
#     base = "Python is simple."
#     merged = "Python is simple and versatile."
#     
#     # Mock query_o4 if needed for standalone test
#     decision, ratings, raw = await judge_quality(base, merged, q)
#     print(f"\nDecision: {decision}")
#     print(f"Ratings: {ratings}")

# if __name__ == "__main__":
#     asyncio.run(main_test()) 

# --- V4 Judge Logic --- 

def _parse_judge_v4_decision(text: str) -> Tuple[str, str]:
    """Parses the V4 judge output (Accept/Reject and optional reasoning)."""
    decision = "Error"
    reasoning = ""
    decision_match = re.search(r"Overall Decision:\s*\[?(Accept|Reject)\]?", text, re.IGNORECASE | re.MULTILINE)
    if decision_match:
        decision = decision_match.group(1).capitalize()
    else:
        logger.warning(f"Could not parse V4 Judge decision from: {text[:200]}...")
        decision = "Error: Cannot Parse Decision" # More specific error
        
    reasoning_match = re.search(r"Reasoning:\s*(.*)", text, re.IGNORECASE | re.MULTILINE)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
        
    return decision, reasoning

async def judge_quality_v4(
    synthesized_answer: str, 
    question: str
) -> Tuple[str, str, str]: # Returns: decision, reasoning, raw_response
    """
    Uses an LLM for an intrinsic quality check of the V4 synthesized answer.

    Args:
        synthesized_answer: The final answer produced by the V4 synthesis step.
        question: The original user question.

    Returns:
        A tuple containing:
        - decision (str): "Accept" or "Reject" (or "Error...").
        - reasoning (str): Optional reasoning provided by the judge.
        - raw_judge_response (str): The raw text output from the judge LLM.
    """
    if not synthesized_answer:
        return "Error: Missing Answer", "", "Synthesized answer was empty."
        
    prompt = JUDGE_V4_PROMPT_TEMPLATE.format(
        question=question,
        synthesized_answer=synthesized_answer
    )
    
    logger.info("Calling V4 Judge Agent...")
    # logger.debug(f"V4 Judge Prompt:\n{prompt[:500]}...")

    raw_judge_response = "Error: Judge LLM query failed."
    decision = "Error"
    reasoning = ""
    
    try:
        # Assuming O4 is suitable for judging V4 as well
        raw_judge_response = await query_o4(prompt)
        logger.debug(f"V4 Judge Agent Raw Response:\n{raw_judge_response}")
        console.print("[bold white][V4 Judge Agent Raw Response][/bold white]")
        console.print(raw_judge_response)
        
        decision, reasoning = _parse_judge_v4_decision(raw_judge_response)
        logger.info(f"V4 Judge Parsed Decision: {decision}, Reasoning: {reasoning}")
        console.print(f"[bold cyan][V4 Judge Parsed Decision]:[/bold cyan] {decision}")
        if reasoning:
             console.print(f"[bold cyan][V4 Judge Reasoning]:[/bold cyan] {reasoning}")
            
    except Exception as e:
        logger.error("Error during V4 judge query.", exc_info=True)
        raw_judge_response = f"Error: Failed to get V4 judge response. {e}"
        decision = "Error: LLM Call Failed"
        reasoning = str(e)

    return decision, reasoning, raw_judge_response

# Example (for testing structure)
# async def main_test():
#     q = "What is the best language?"
#     base = "Python is simple."
#     merged = "Python is simple and versatile."
#     
#     # Mock query_o4 if needed for standalone test
#     decision, ratings, raw = await judge_quality(base, merged, q)
#     print(f"\nDecision: {decision}")
#     print(f"Ratings: {ratings}")

# if __name__ == "__main__":
#     asyncio.run(main_test()) 