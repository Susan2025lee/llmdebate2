# Agent Interaction and Prompt Usage by Version

This document outlines the workflow, agent interactions, and specific prompt templates used in each version of the multi-LLM debate system for easy comparison.

---

## Version 1 (`debate.py` - Factor-Centric, Inferred)

*   **Goal:** Basic proof-of-concept using structured factor exchange. Quality might be limited by factor representation.
*   **Entry Point:** `debate.py`

**Workflow:**

1.  **Initial Factors (All Agents):**
    *   Each agent (O4, Gemini, Grok) independently generates an initial list of factors (JSON) based on the question.
    *   **Prompt Used:** `BASELINE_PROMPT_TEMPLATE` (defined in `utils/prompts.py`) - Asks for JSON factors.

2.  **Debate Rounds (All Agents):**
    *   Agents iteratively critique and revise their factor lists.
    *   Input to each agent includes its previous factors and other agents' factors (JSON).
    *   **Prompt Used:** Likely an early version of `CRITIQUE_PROMPT_TEMPLATE` (or similar logic) designed to output revised *factors* (JSON).
    *   Human feedback (text) can be incorporated.

3.  **Merge Factors (Algorithmic - Initially):**
    *   *Note: Early V1 likely used a simple algorithm (endorsement count, confidence threshold) to merge the final factor lists.*
    *   Later versions might have retroactively used the V2/V3 LLM-based merge.

4.  **Summarize (LLM):**
    *   Generate a final prose answer based *only* on the merged factors.
    *   **Prompt Used:** `SUMMARIZATION_PROMPT_TEMPLATE` (defined in `utils/prompts.py`)

5.  **Judge (LLM):**
    *   Compares the final prose summary against the *initial factors* (JSON) from the baseline agent (e.g., O4-mini).
    *   **Prompt Used:** `JUDGE_PROMPT_TEMPLATE` (defined in `utils/prompts.py`), adapted to handle prose vs. factor comparison.

---

## Version 2 (`debate_v2.py` - Prose Baseline + Factor Debate)

*   **Goal:** Improve quality by starting with a strong prose baseline, then using factor debate for refinement.
*   **Entry Point:** `debate_v2.py`

**Workflow:**

1.  **Initial Prose Baseline (Anchor Agent):**
    *   One designated agent (e.g., O4-mini) generates a comprehensive prose baseline.
    *   **Prompt Used:** `PROSE_BASELINE_GENERATION_TEMPLATE` (defined in `utils/prompts.py`)

2.  **Critique Baseline -> Initial Factors (All Agents):**
    *   All agents critique the single prose baseline and output their initial *factors* (JSON) based on this critique.
    *   **Prompt Used:** `CRITIQUE_PROSE_BASELINE_TEMPLATE` (defined in `utils/prompts.py`)

3.  **Debate Rounds (All Agents):**
    *   Agents iteratively critique and revise their *factor* lists.
    *   Input includes previous factors (JSON) from self and others.
    *   **Prompt Used:** `CRITIQUE_PROMPT_TEMPLATE` (defined in `utils/prompts.py`) - Takes factors, outputs factors.
    *   Human feedback (text) can be incorporated.

4.  **Merge Factors (LLM):**
    *   An LLM merges the final factor lists from all agents into a synthesized, ranked list of top-k factors (JSON).
    *   **Prompt Used:** `MERGE_FACTORS_PROMPT` (defined in `utils/prompts.py`)

5.  **Summarize (LLM):**
    *   Generate a final prose summary based *only* on the LLM-merged factors.
    *   **Prompt Used:** `SUMMARIZATION_PROMPT_TEMPLATE` (defined in `utils/prompts.py`)

6.  **Judge (LLM):**
    *   Compares the final prose *summary* against the initial *prose baseline* from the anchor agent.
    *   **Prompt Used:** `JUDGE_PROMPT_TEMPLATE` (defined in `utils/prompts.py`)

---

## Version 3 (`debate_v3.py` - Integrated Refinement)

*   **Goal:** Enhance V2 by integrating debate insights back into the detailed prose baseline, preserving more nuance.
*   **Entry Point:** `debate_v3.py`

**Workflow:**

1.  **Initial Prose Baseline (Anchor Agent):** Same as V2.
    *   **Prompt Used:** `PROSE_BASELINE_GENERATION_TEMPLATE`
2.  **Critique Baseline -> Initial Factors (All Agents):** Same as V2.
    *   **Prompt Used:** `CRITIQUE_PROSE_BASELINE_TEMPLATE`
3.  **Debate Rounds (All Agents):** Same as V2.
    *   **Prompt Used:** `CRITIQUE_PROMPT_TEMPLATE`
4.  **Merge Factors (LLM):** Same as V2.
    *   **Prompt Used:** `MERGE_FACTORS_PROMPT`
5.  **Summarize (LLM):** Same as V2.
    *   **Prompt Used:** `SUMMARIZATION_PROMPT_TEMPLATE`
6.  **Refine Baseline (LLM):**
    *   An LLM integrates the `debate_summary` (from step 5) into the `initial_prose_baseline` (from step 1).
    *   **Prompt Used:** `REFINE_PROMPT_TEMPLATE` (defined in `utils/prompts.py`)
7.  **Judge (LLM):**
    *   Compares the *refined* prose answer (from step 6) against the *initial prose baseline* (from step 1).
    *   **Prompt Used:** `JUDGE_PROMPT_TEMPLATE`

---

## Version 4: Parallel Baselines & Free-Form Critique (`debate_v4.py`)

*   **Goal:** Maximize perspective diversity early, synthesize comprehensive answers.
*   **Entry Point:** `debate_v4.py`
*   **Workflow:**
    1.  **Parallel Prose Baselines:** Generate initial comprehensive prose answers from *multiple* LLM agents concurrently.
        *   Prompt: `PROSE_BASELINE_GENERATION_TEMPLATE` (Common prompt for all agents).
    2.  **Free-Form Critique Round(s):** Each agent receives its own baseline and the baselines of *all other* agents. It provides a free-form critique and comparison.
        *   Prompt: `FREEFORM_CRITIQUE_PROMPT_TEMPLATE`
    3.  **Synthesis (Two Options):**
        *   **Option A (V4 Default):** A dedicated synthesizer LLM takes the original question, *all* initial baselines, and *all* critique texts to generate a single, comprehensive final answer.
            *   Prompt: `SYNTHESIS_PROMPT_TEMPLATE`
        *   **Option B (V3 Refine Style):** Integrates the critique texts into the baseline generated by a single reference agent (e.g., O4-mini), mimicking the V3 refinement step.
            *   Prompt: `REFINE_PROMPT_TEMPLATE` (Uses reference baseline + concatenated critiques as `debate_summary`)
    4.  **Judge:** Compares the final synthesized answer (from Option A or B) against the reference baseline (e.g., O4-mini).
        *   Prompt: `JUDGE_PROMPT_TEMPLATE` (same as V3) 