# PRD: CLI-Based Multi-LLM Debate System

## 1. Overview
A command-line proof-of-concept that validates a structured debate protocol among multiple LLMs (O4-mini, Gemini 2.5, Grok 3). The tool will:

- Fan out a user's question to each model in parallel.
- Conduct iterative debate rounds with optional human feedback.
- Merge outputs via endorsement and confidence logic.
- Summarize consensus into a final answer.
- Guard quality with a judge agent.

### System Approaches

*   **Version 1 (`debate.py`):** Focuses on structured data exchange (JSON factors) throughout.
*   **Version 2 (`debate_v2.py`):** Generates a high-quality prose baseline, uses debate rounds to critique/refine factors, then synthesizes a summary from the top K debated factors. Judge compares baseline prose vs. final *summarized* debate factors.
*   **Version 3 (`debate_v3.py` - Proposed):** Builds on V2. After synthesizing the top K debated factors into a summary, it uses a second LLM call to *integrate* that summary's insights back into the original prose baseline, aiming to preserve baseline detail while incorporating debate refinements. Judge compares baseline prose vs. this final *integrated* prose.
*   **Version 4 (`debate_v4.py` - Proposed):** Aims to maximize perspective diversity and detail preservation. 
    *   Generates *parallel prose baselines* from all participating agents.
    *   Conducts one or more rounds of *free-form text debate* where agents critique each other's prose arguments directly.
    *   Employs a final *synthesis step* where a high-capability LLM reads the entire history (parallel baselines + free-form debate) to generate the final, comprehensive prose answer. 
    *   Eliminates structured factor extraction/merging during the debate.

## 2. Objectives & Success Criteria
| Objective                              | Success Criterion                            |
|----------------------------------------|----------------------------------------------|
| Validate debate workflow               | End-to-end debate completes without errors   |
| Ensure answer ≥ baseline quality       | Judge agent approves merged answer ≥ baseline |
|                                        | (V1: Prose Merged vs JSON Baseline; V2: Prose Merged vs Prose Baseline; V3: Integrated Prose vs Prose Baseline; **V4: Synthesized Prose vs. *Average/Best* Initial Baseline (TBD)**) |
| Human-in-the-loop integration          | User feedback incorporated between rounds (Note: V4 Human feedback integration TBD) |
| Core merge logic accuracy              | Consensus factors correctly identified (N/A for V4 - relies on Synthesis step) |
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
5. **Merge Logic (V2/V3 Component)**: Aggregate factors using an LLM call to identify distinct concepts, synthesize representative factors, rank them, and return the top K. This synthesized result feeds the summarizer.
6. **Summarization (V2/V3 Component)**: Generate final prose summary from consensus factors identified by the merge logic.
7. **Refinement Logic (V3 Only)**: Use an LLM call to integrate the debate summary (from step 6) back into the original prose baseline, producing a refined final answer.
8. **Judge Quality Guard**: Compare final answer vs. baseline; fallback if needed.
    *   *V1 Note: Compares final prose summary vs. baseline agent's raw JSON factor list.*
    *   *V2 Note: Compares final prose summary vs. initial high-quality prose baseline.*
    *   *V3 Note: Compares final *integrated* prose answer vs. initial high-quality prose baseline.*
9. **Logging**: Persist full transcript and scores to JSON.
10. **Web Interface (Basic)**: Provide a simple web UI (Flask) to input a question and display the final generated answer.

**V4 Specific Requirements:**
11. **Parallel Baseline Generation (V4):** Query *all* participating agents in parallel for initial *prose* answers to the question.
12. **Free-Form Debate Rounds (V4):** Conduct one or more rounds where agents exchange critiques and arguments in *free-form text*, referencing the previous round's text and/or initial baselines.
13. **Synthesis Step (V4):** Use a final LLM call to read all generated baselines and free-form debate text, producing a single synthesized prose answer.
14. **V4 Structure:** Implement V4 logic in a new file (e.g., `debate_v4.py`) to allow comparison with V3.
15. **V4 Web UI:** Update the web interface to display parallel baselines and free-form debate content.

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
| **V4: Parallel Baselines** | **All agents generate prose baselines**    | **Day 4** |
| **V4: Free-Form Critique**| **Implement 1 round of text critique**   | **Day 4** |
| **V4: Synthesis Step**    | **Implement final synthesis prompt/call**| **Day 5** |
| **V4: Integration & Web UI**| **Integrate V4 flow, update UI**       | **Day 5** |

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