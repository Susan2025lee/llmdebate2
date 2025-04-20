# Task List: CLI-Based Multi-LLM Debate System

## Milestone 1: Baseline & Fan‑Out
- [x] Scaffold project (files, virtualenv, requirements)
- [x] Setup CLI with `typer` and env loading
- [x] Implement OpenAI (O4-mini) async wrapper
- [ ] Implement Gemini 2.5 async wrapper (using direct API calls, reading GEMINI_API_KEY/GEMINI_MODEL from .env)
- [ ] Implement Grok 3 async wrapper (skipped)
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
- [x] Code merge logic (endorsement + confidence) - *Initial version*
- [ ] Enhance merge logic with semantic clustering (using `sentence-transformers`)
- [x] Create summarization prompt and integration (in core/summarizer.py)
- [x] Test final summarization (Via smoke test)
- [x] Write unit tests for merge logic calculations - *Covers initial version*
- [ ] Write unit tests for semantic merge logic
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

## Version 2: Critique Prose Baseline (In Progress)

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
- [ ] Perform manual testing with rich prompts 