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
- Implement merge logic:
  ```python
  # Basic approach: Count endorsements + average confidence
  endorsements = Counter()
  confidences = defaultdict(list)
  for agent in agents:
      for factor in agent.factors:
          endorsements[factor.name] += 1
          confidences[factor.name].append(factor.confidence)
  # Filter and sort
  ```
- **Enhance merge logic**: Implement semantic clustering (e.g., using sentence embeddings) to group similar factors before ranking, improving synthesis quality.
- Create summarization prompt using merged factors + justifications.
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