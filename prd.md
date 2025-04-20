# PRD: CLI-Based Multi-LLM Debate System

## 1. Overview
A command-line proof-of-concept that validates a structured debate protocol among multiple LLMs (O4-mini, Gemini 2.5, Grok 3). The tool will:

- Fan out a user's question to each model in parallel.
- Conduct iterative debate rounds with optional human feedback.
- Merge outputs via endorsement and confidence logic.
- Summarize consensus into a final answer.
- Guard quality with a judge agent.

### System Approaches

*   **Version 1 (`debate.py`):** The initial implementation focuses on structured data exchange. It prompts all agents for a *JSON list of factors* in the baseline step. The debate proceeds using these JSON factors, and the final merged summary (prose) is compared against the baseline agent's raw JSON factor list by the judge.
*   **Version 2 (`debate_v2.py` - Planned):** A revised approach focused on maximizing final answer quality. It first generates a high-quality *prose* baseline answer from a primary "Anchor Agent". Other agents then *critique* this prose baseline in the first round, generating JSON factors to seed the debate. Subsequent rounds refine these factors. The judge compares the initial prose baseline against the final merged prose summary.

## 2. Objectives & Success Criteria
| Objective                              | Success Criterion                            |
|----------------------------------------|----------------------------------------------|
| Validate debate workflow               | End-to-end debate completes without errors   |
| Ensure answer ≥ baseline quality       | Judge agent approves merged answer ≥ baseline |
|                                        | (V1: Prose Merged vs JSON Baseline; V2: Prose Merged vs Prose Baseline) |
| Human-in-the-loop integration          | User feedback incorporated between rounds     |
| Core merge logic accuracy              | Consensus factors correctly identified       |
| Time-to-PoC                            | ≤ 1 day developer effort                     |

## 3. User Stories
- **Developer**: Runs `python debate.py`, enters a question, inspects each round in the terminal.
- **Domain Expert**: Reviews factors, provides feedback when prompted.
- **Judge Agent**: Automates quality check, fallback to baseline if needed.
- **End User**: Receives a concise, evidence-backed answer.

## 4. Functional Requirements
1. **CLI Prompt**: Ask user for a question.
2. **Baseline & Fan‑Out**: Query O4-mini, Gemini 2.5, Grok 3 in parallel for factor lists.
3. **Debate Rounds**: Each agent critiques and revises in parallel; include human feedback.
4. **Convergence Check**: Halt if changes fall below a threshold or after max rounds.
5. **Merge Logic**: Aggregate factors by endorsement count and mean confidence. Enhancement planned to incorporate semantic similarity for improved synthesis.
6. **Summarization**: Generate final prose answer from consensus factors.
7. **Judge Quality Guard**: Compare merged vs. baseline; fallback if merged underperforms.
    *   *V1 Note: Compares final prose summary vs. baseline agent's raw JSON factor list.*
    *   *V2 Note: Compares final prose summary vs. initial high-quality prose baseline.*
8. **Logging**: Persist full transcript and scores to JSON.

## 5. Non-Functional Requirements
- **Simplicity**: Single script or minimal modules.
- **Performance**: Async calls via `asyncio.gather`.
- **Portability**: Python 3.10+; cross-platform.
- **Minimal Dependencies**: ≤5 external libraries (OpenAI SDK, etc.).
- **Development Environment**: Use Python virtual environment (`venv`) for dependency isolation.
- **LLM Access**: All calls to LLMs must go through the `LLMInterface` class (`src/core/llm_interface.py`) to ensure consistent proxy configuration and model-specific adaptations.

## 6. Milestones & Roadmap
| Step                    | Deliverable                               | ETA   |
|-------------------------|-------------------------------------------|-------|
| Baseline + Fan‑Out      | Parallel LLM queries + prints             | Day 1 |
| Debate Loop             | Structured rounds + human feedback        | Day 2 |
| Merge & Summarize       | Merge logic + summarizer prompt           | Day 2 |
| Judge Agent Integration | Quality guard + fallback flow             | Day 3 |
| CLI & Logging Polish    | Config flags + transcript export          | Day 3 |

## Appendix
**Sample CLI Run**:
```bash
$ python debate.py --max-rounds 3 --top-k 5
Question: What drives EV market success?
[Baseline] O4-mini: Factor A, B, C (confidences)

[Round 1]
Agent 0 (O4): …
Agent 1 (Gemini): …
Agent 2 (Grok): …
Feedback: Consider charging infrastructure.

[Merge] Consensus: A, B, Infrastructure
[Summarizer] Final Answer: …
[Judge] Baseline: Pass, Merged: Pass → Accept
``` 