# Implementation Plan: CLI-Based Multi-LLM Debate System

## Milestone 1: Baseline & Fan‑Out
- Setup project structure (`debate.py`, `requirements.txt`, `.env`).
- Install dependencies: `openai`, `google-palm`, `grok-client`, `typer`, `python-dotenv`, `asyncio`.
- Initialize CLI using `typer`:
  ```python
  import typer
  app = typer.Typer()
  @app.command()
  def main(question: str, max_rounds: int = 3, top_k: int = 5):
      pass
  if __name__ == '__main__':
      app()
  ```
- Implement async LLM client wrappers:
  - `async def query_o4(prompt: str) -> List[Factor]`
  - `async def query_gemini(prompt: str) -> List[Factor]`
  - `async def query_grok(prompt: str) -> List[Factor]`
- Build baseline prompt template.
- In `main()`, gather baseline + parallel calls:
  ```python
  baseline = await query_o4(prompt)
  results = await asyncio.gather(query_o4(prompt), query_gemini(prompt), query_grok(prompt))
  ```
- Print formatted outputs to console.

## Milestone 2: Debate Loop
- Define data structures: `AgentResult { factors, confidences, justifications }`.
- Write round prompt template with self + peer context.
- Loop up to `max_rounds`:
  - For each agent, assemble critique prompt.
  - Call `asyncio.gather` for all agents.
  - Print each agent's revision.
  - Prompt user with `input()` for feedback.
  - Append feedback to next-round context.
  - Check for convergence (Δ threshold on confidences / factor sets).

## Milestone 3: Merge & Summarize
- Implement **LLM-based merge logic** (`core/merge_logic.py`):
    - Refactor `merge_factors` to be `async`.
    - Design prompt instructing LLM (e.g., O4-mini via `LLMInterface`) to:
        - Accept a list of factors from all agents.
        - Group factors by semantic meaning.
        - Synthesize a representative factor (name, justification, confidence) for each distinct group.
        - Rank synthesized factors based on importance/support.
        - Return the top `k` factors in a reliable JSON format.
    - Implement logic to format input factors for the prompt.
    - Implement LLM call using `LLMInterface`.
    - Implement robust parsing for the LLM's JSON output.
- Create summarization prompt using the LLM-merged factors.
- Query summarizer LLM and print final prose answer.

## Milestone 4: Judge Agent Integration
- Build judge prompt template comparing baseline vs. merged.
- Query judge LLM, parse ratings.
- If any rating < threshold, set final answer = baseline.
- Print judge results and final decision.

## Milestone 5: CLI & Logging Polish
- Add verbose and quiet flags in `typer` CLI.
- Integrate `rich` for colored output and spinners.
- Implement JSON transcript logging:
  ```python
  transcript = { 'baseline': ..., 'rounds': [...], 'merge': ..., 'judge': ... }
  with open('transcript.json', 'w') as f: json.dump(transcript, f)
  ```
- Add `--output` flag for transcript file path.
- Write README with setup and usage instructions.

## Version 2 Implementation Plan (Critique Prose Baseline)

This version aims to improve answer quality by generating a high-quality prose baseline first and then using the debate rounds to critique and refine it.

1.  **Copy Entry Point:** Create `debate_v2.py` by copying `debate.py`.
2.  **New Prompts (`utils/prompts.py`):**
    *   Add `PROSE_BASELINE_GENERATION_TEMPLATE`: Takes `{question}`, asks for a comprehensive prose answer.
    *   Add `CRITIQUE_PROSE_BASELINE_TEMPLATE`: Takes `{question}`, `{prose_baseline}`, asks critique agents to critique the prose and output a JSON factor list based on the critique.
    *   (Optional) Add `SELF_CRITIQUE_PROSE_BASELINE_TEMPLATE`: Takes `{question}`, `{prose_baseline}`, asks anchor agent to critique its own prose and output a JSON factor list.
3.  **Modify Baseline Flow (`debate_v2.py`):**
    *   Designate an "Anchor Agent" (e.g., O4-mini, make configurable).
    *   **Initial Prose Call:** Call the Anchor Agent with `PROSE_BASELINE_GENERATION_TEMPLATE` to get `prose_baseline`.
    *   **Critique/Factor Calls (Round 1 Seed):**
        *   Call Critique Agents (e.g., Gemini) with `CRITIQUE_PROSE_BASELINE_TEMPLATE` (passing `prose_baseline`).
        *   Call Anchor Agent with its self-critique template (passing `prose_baseline`).
        *   Parse the JSON factor lists from these calls using `_parse_factor_list`.
        *   Store these results as the `initial_responses` to pass to `run_debate_rounds`.
    *   Update transcript logging for the new steps.
4.  **Verify Debate Loop (`core/debate_engine.py`):**
    *   Ensure the main loop handles the `initial_responses` from the critique step correctly.
    *   Confirm round numbering/logging is appropriate.
5.  **Update Judge Integration (`debate_v2.py`):**
    *   Ensure `judge_quality` compares `prose_baseline` against the `final_merged_summary`.
    *   Ensure fallback logic uses `prose_baseline`.
6.  **Configuration:** Add option to select Anchor Agent (e.g., in `.env` or `config.json`).
7.  **Testing:**
    *   Manual testing with rich prompts.
    *   Update/add unit tests for the modified flow in `debate_v2.py`.

## Version 3 Implementation Plan (Integrated Refinement)

This version builds on V2 by adding a dedicated step to integrate debate insights back into the original baseline, preserving detail while adding refinement.

1.  **Setup:**
    *   Create `debate_v3.py` (e.g., by copying `debate_v2.py`).
    *   Ensure V2 components (prose baseline, critique seeding, debate rounds, LLM merge, summarization) are functional.
2.  **Refinement Function (`core/refiner.py` or `core/merge_logic.py`):
    *   Create `async def refine_with_debate_summary(baseline_prose: str, debate_summary: str, question: str) -> str`.
    *   Design `REFINE_PROMPT_TEMPLATE`: Instruct LLM (e.g., O4-mini via `LLMInterface`) to enhance `baseline_prose` by integrating insights from `debate_summary`, preserving baseline structure/detail.
    *   Implement LLM call within the function.
3.  **Modify Main Flow (`debate_v3.py`):
    *   After generating `final_summary` from merged factors, call `await refine_with_debate_summary()` passing the original `prose_baseline` and the `final_summary`.
    *   Store the result as `refined_answer`.
4.  **Update Judge Integration (`debate_v3.py`):
    *   Modify the call to `judge_quality` to pass `merged_answer=refined_answer`.
    *   Update final selection logic to use `refined_answer` if the judge approves it.
5.  **Testing:**
    *   Manual testing comparing `refined_answer` vs. `prose_baseline`.
    *   Add/update unit tests for the new refinement function and modified `debate_v3.py` flow.

## Version 4 Implementation Plan (Parallel Baselines & Free-Form Debate)

This version represents a significant architectural shift, prioritizing diverse perspectives and detailed discussion over structured factor extraction during the debate.

1.  **Setup & Preservation:**
    *   Create `debate_v4.py` by copying `debate_v3.py` to preserve the V3 working version.
    *   Create a new core logic module if needed (e.g., `core/debate_engine_v4.py`) to house the new debate flow, keeping `core/debate_engine.py` untouched for V3.
2.  **Parallel Prose Baseline Generation (`debate_v4.py`):**
    *   Modify the initial step to call *all* configured agents (O4-mini, Gemini, Grok if present) using the existing `PROSE_BASELINE_GENERATION_TEMPLATE`.
    *   Store these multiple prose baselines (e.g., in a dictionary `initial_baselines: Dict[str, str]`).
    *   Update transcript logging.
3.  **Free-Form Critique/Debate Prompts (`utils/prompts.py`):**
    *   Define `FREEFORM_CRITIQUE_PROMPT_TEMPLATE`: Takes the agent's own baseline and all other baselines. Instructs the agent to compare, critique, and state its core arguments in *prose*.
    *   Define `FREEFORM_DEBATE_ROUND_PROMPT_TEMPLATE`: Takes the full text history from the previous free-form round. Instructs the agent to respond, critique, and refine its arguments in *prose*.
4.  **Free-Form Debate Logic (`core/debate_engine_v4.py` or similar):**
    *   Implement `async def run_freeform_critique_round(initial_baselines: Dict[str, str]) -> Dict[str, str]`: Calls all agents with the `FREEFORM_CRITIQUE_PROMPT_TEMPLATE`.
    *   Implement `async def run_freeform_debate_round(previous_round_texts: Dict[str, str]) -> Dict[str, str]`: Calls all agents with `FREEFORM_DEBATE_ROUND_PROMPT_TEMPLATE`. (Start with only implementing/calling the critique round).
    *   Update `debate_v4.py` to call these new functions.
    *   Remove calls to factor parsing (`_parse_factor_list`), existing `run_debate_rounds`, factor merging (`merge_factors`), summarization (`generate_summary`), and refinement (`refine_with_debate_summary`).
5.  **Synthesis Step (`core/synthesizer.py` or similar):**
    *   Create `async def synthesize_final_answer(question: str, initial_baselines: Dict[str, str], debate_texts: List[Dict[str, str]]) -> str`.
    *   Design `SYNTHESIS_PROMPT_TEMPLATE`: Instructs a high-capability LLM (e.g., O4-mini or judge model) to read the question, all baselines, and all free-form debate text, then synthesize a single, comprehensive prose answer.
    *   Implement the LLM call within this function.
    *   Update `debate_v4.py` to call this function after the free-form round(s) to get the `final_synthesized_answer`.
6.  **Judge Integration (V4 Adaptation):**
    *   Decide how the judge should operate in V4. Options:
        *   Compare `final_synthesized_answer` vs. one of the `initial_baselines` (e.g., the anchor agent's or a randomly chosen one).
        *   Compare `final_synthesized_answer` vs. an average/representative baseline (harder to define).
        *   Judge the `final_synthesized_answer` on its own merits using a different rubric/prompt.
    *   Modify the judge call in `debate_v4.py` accordingly.
7.  **Web UI Update (`templates/index.html`, `app.py`):**
    *   Modify `app.py` to call the V4 debate logic (`debate_v4.py`).
    *   Add new progress callback event types for parallel baselines and free-form debate rounds.
    *   Update `index.html` JavaScript to handle these new event types.
    *   Add HTML sections to display multiple baselines and the free-form text responses.
    *   Ensure the final synthesized answer is displayed.
8.  **Testing:**
    *   Extensive manual testing comparing V4 outputs against V3 outputs for quality, detail, and perspective diversity.
    *   Unit tests for new core logic functions (free-form rounds, synthesizer).

## Milestone 6: Basic Web Interface (Flask)

- **Dependencies:** Add `Flask` to `requirements.txt` and install.
- **File Structure:**
    - Create `app.py` at the project root.
    - Create `templates/` directory.
    - Create `templates/index.html`.
- **Flask App (`app.py`):**
    - Initialize Flask app.
    - Define route (`/`) supporting GET and POST.
    - GET handler: Render `index.html`.
    - POST handler:
        - Get `question` from form.
        - Import `run_debate_logic` from `debate_v3.py`.
        - **Adapt `run_debate_logic`**: Modify it (or create a wrapper) to return the final answer string instead of just printing/logging.
        - Run the adapted logic (using `asyncio.run()` for initial simplicity).
        - Render `index.html` passing the result back for display.
- **HTML Template (`templates/index.html`):**
    - Basic HTML structure.
    - Form with `<textarea name="question">` and submit button.
    - Display area for the result using Jinja2 (`{{ result }}`). 