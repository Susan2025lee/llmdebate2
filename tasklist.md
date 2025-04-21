# Task List: CLI-Based Multi-LLM Debate System

## Milestone 1: Baseline & Fan‑Out
- [x] Scaffold project (files, virtualenv, requirements)
- [x] Setup CLI with `typer` and env loading
- [x] Implement OpenAI (O4-mini) async wrapper
- [ ] Implement Gemini 2.5 async wrapper (using direct API calls, reading GEMINI_API_KEY/GEMINI_MODEL from .env)
- [ ] Implement Grok 3 async wrapper (`llm_clients/grok_client.py`) **(Skipped - Focus on O4-mini & Gemini)**
- [x] Build and test baseline & parallel fan‑out logic (initial version with stubs/placeholders)
- [ ] Write unit tests for LLM client wrappers
- [x] Write unit tests for O4 LLM client wrapper (via LLMInterface)
- [x] Write unit tests for Gemini client wrapper (direct API calls)
- [x] Write unit tests for baseline & parallel fan‑out logic

## Milestone 2: Debate Loop
- [ ] Define `AgentResult` data structures
- [x] Define `AgentResult` data structures (Factor, AgentResponse in utils/models.py)
- [x] Create critique prompt templates (in utils/prompts.py)
- [x] Implement debate loop with parallel rounds (in core/debate_engine.py)
- [x] Add human feedback integration via `input()`
- [x] Implement convergence detection logic
- [x] Write unit tests for debate loop logic (including feedback and convergence)
- [x] Write unit tests for convergence detection logic (covered by debate loop tests)

## Milestone 3: Merge & Summarize
- [x] Code merge logic (endorsement + confidence) - *Initial basic version*
- [x] Create summarization prompt and integration (in core/summarizer.py)
- [x] Test final summarization (Via smoke test)
- [x] Write unit tests for basic merge logic calculations
- [x] Write unit tests for summarization prompt assembly (in tests/test_summarizer.py)

## Milestone 4: Judge Agent Integration
- [ ] Build judge agent prompt and wrapper
- [x] Build judge agent prompt and wrapper (in judge/judge_agent.py)
- [x] Integrate judge fallback flow
- [ ] Fix Judge Agent input to compare prose vs. prose (`debate.py`)
- [x] Write unit tests for judge agent prompt and fallback logic
- [x] Write unit tests for judge agent prompt and fallback logic (in tests/test_judge_agent.py)

## Milestone 5: CLI & Logging Polish
- [ ] Add CLI flags (verbose, output path)
- [x] Integrate `rich` for output styling and spinners
- [x] Implement logging (standard library) and JSON transcript export
- [ ] End-to-end smoke test
- [ ] Write unit tests for logging setup
- [ ] Write unit tests for JSON transcript export
- [x] Implement JSON-based Factor Parsing in `_parse_factor_list` (`core/debate_engine.py`) - Replaced regex parsing
- [x] Add Unit Tests for `_parse_factor_list` (`tests/test_debate_engine.py`)
- [x] Implement Factor Merging Logic (`core/merge_logic.py`) - Verified via smoke test
- [x] Implement Final Summarization (`core/summarizer.py`) - Verified via smoke test

## Core Logic
- [x] Implement Baseline Fan-Out Logic (`debate.py`)
- [x] Implement Multi-Round Debate Logic (`core/debate_engine.py`)
- [x] Implement JSON-based Factor Parsing in `_parse_factor_list` (`core/debate_engine.py`) - Replaced regex parsing
- [x] Add Unit Tests for `_parse_factor_list` (`tests/test_debate_engine.py`)
- [ ] Implement Factor Merging Logic (`core/merge_logic.py`)
- [ ] Implement Final Summarization (`core/summarizer.py`)

## Version 2: Critique Prose Baseline (Foundation for V3)

- [x] Create `debate_v2.py` (copy from `debate.py`)
- [x] Add new prompt templates to `utils/prompts.py` (`PROSE_BASELINE_GENERATION_TEMPLATE`, `CRITIQUE_PROSE_BASELINE_TEMPLATE`)
- [x] Implement Anchor Agent configuration (reading `ANCHOR_AGENT_NAME` from `.env`)
- [x] Modify baseline flow in `debate_v2.py`:
    - [x] Add initial prose baseline generation step
    - [x] Implement critique/factor generation step for Round 1 seeding
    - [x] Update transcript logging
- [ ] Verify/adjust debate loop logic in `core/debate_engine.py` if needed (e.g., round numbering) - *Deferred pending testing*
- [x] Update judge integration in `debate_v2.py` (prose vs. prose comparison, fallback logic)
- [ ] Add/update unit tests for `debate_v2.py` flow
- [x] Enhance Factor Merging Logic (`core/merge_logic.py`):
    - [x] Refactor `merge_factors` to use LLM for high-quality synthesis
    - [x] Make `merge_factors` async
    - [x] Design/implement prompt for LLM-based merging (grouping, synthesis, ranking)
    - [x] Implement LLM call via `LLMInterface`
    - [x] Implement robust JSON parsing for LLM output
    - [ ] Write unit tests for LLM-based merge logic (mocking LLM call, testing parsing)
- [x] Perform manual testing with rich prompts

## Version 3: Integrated Refinement (Planned)

- [x] Create `debate_v3.py` (copy from `debate_v2.py`)
- [x] Define/Implement Refinement Step:
    - [x] Create `async def refine_with_debate_summary(...)` function (in `core/merge_logic.py` for now)
    - [x] Design `REFINE_PROMPT_TEMPLATE` for integrating debate summary into baseline prose (in `utils/prompts.py`)
    - [x] Implement LLM call within the refinement function
- [x] Modify `debate_v3.py` Flow:
    - [x] Call `refine_with_debate_summary` after summarization step
    - [x] Pass refined answer to `judge_quality`
    - [x] Update final answer selection logic
- [ ] Write unit tests for refinement function and `debate_v3.py` flow
- [x] Perform manual testing comparing V3 integrated output vs. baseline.

## Version 4: Parallel Baselines & Free-Form Debate (Planned)

- [x] Create `debate_v4.py` (e.g., copy `debate_v3.py`)
- [x] Create new core logic module (`core/debate_engine_v4.py`?)
- [x] Modify `debate_v4.py`: Implement parallel prose baseline generation (all agents)
- [x] Update transcript logging for V4 baselines
- [x] Define `FREEFORM_CRITIQUE_PROMPT_TEMPLATE` in `utils/prompts.py`
- [ ] Define `FREEFORM_DEBATE_ROUND_PROMPT_TEMPLATE` in `utils/prompts.py` (for future multi-round)
- [x] Implement `run_freeform_critique_round` (e.g., in `core/debate_engine_v4.py`)
- [ ] Implement `run_freeform_debate_round` (for future multi-round)
- [x] Modify `debate_v4.py`: Call critique round, remove old factor/merge/refine/summarize calls
- [x] Define `SYNTHESIS_PROMPT_TEMPLATE` in `utils/prompts.py`
- [x] Implement `synthesize_final_answer` function (e.g., in `core/synthesizer.py`)
- [x] Modify `debate_v4.py`: Call synthesis function to get final answer
- [x] Decide on V4 judge strategy and implement
- [x] Modify `app.py` to optionally call `debate_v4.py` logic
- [x] Add V4 progress event types to `app.py` callbacks
- [x] Update `index.html` JavaScript for V4 events
- [x] Update `index.html` HTML to display parallel baselines and free-form text
- [x] Write unit tests for V4 core logic (critique round, synthesis)
- [ ] Perform extensive manual testing comparing V4 vs V3 outputs

## Milestone 6: Basic Web Interface (Flask - Planned)

- [x] Add Flask dependency to `requirements.txt`
- [x] Create `app.py` with basic Flask app structure
- [x] Create `templates/` directory and `templates/index.html`
- [x] Implement GET route in `app.py` to render `index.html`
- [x] Implement POST route in `app.py`:
    - [x] Get question from form
    - [x] Adapt `debate_v3.run_debate_logic` to return final answer
    - [x] Call adapted logic (using `asyncio.run` initially)
    - [x] Render `index.html` with result
- [x] Create basic HTML form and result display area in `index.html`

## Additional Tasks
- [x] Implement basic V1 debate logic (`debate.py`)
- [x] Implement V2 logic with prose baseline (`debate_v2.py`)
- [x] Implement V3 logic with baseline refinement (`debate_v3.py`)
- [x] Add Judge Agent (`judge/`)
- [x] Add CLI interfaces for V1, V2, V3
- [x] Develop initial Web UI (`app.py`, `templates/index.html`)
- [x] Integrate V1, V2, V3 into Web UI with SSE
- [x] Implement V4 core logic (`debate_v4.py`, `core/debate_engine_v4.py`)
  - [x] Parallel prose baselines
  - [x] Single round free-form critique
  - [x] Synthesizer (V4 Default)
  - [x] Alternative Synthesizer (V3 Refine Style)
- [x] Integrate V4 into Web UI
  - [x] Modify `app.py` to optionally call `debate_v4.py` logic (using Socket.IO)
  - [x] Add V4 progress event types to `app.py` callbacks (using Socket.IO)
  - [x] Update `index.html` JavaScript for V4 events & Socket.IO
  - [x] Update `index.html` HTML to display V4 results (parallel baselines, free-form text, synthesizer choice)
- [x] Write unit tests for V4 core logic (critique round, synthesis)
- [ ] Perform extensive manual testing comparing V4 vs V3 outputs (CLI and Web UI)
- [x] Create `agent_interaction.md` documentation.
- [x] Finalize Documentation (`README.md`, etc.)