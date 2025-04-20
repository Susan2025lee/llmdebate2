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
  endorsements = Counter()
  confidences = defaultdict(list)
  for agent in agents:
      for factor in agent.factors:
          endorsements[factor.name] += 1
          confidences[factor.name].append(factor.confidence)
  # Filter and sort
  ```
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