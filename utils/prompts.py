# utils/prompts.py

BASELINE_PROMPT_TEMPLATE = """
Q: {question}

Identify the top {top_k} factors relevant to the question.
Format your response as a JSON array, where each object represents a factor and has the following keys:
- "factor_name": A string containing the descriptive name of the factor.
- "justification": A string containing 1-2 sentences explaining the factor's relevance.
- "confidence": A number (integer or float) between 1 and 5 (inclusive), with 5 being the highest confidence.

Example format:
[
  {{
    "factor_name": "Example Factor 1",
    "justification": "This is why factor 1 is relevant.",
    "confidence": 4.5
  }},
  {{
    "factor_name": "Example Factor 2",
    "justification": "This is why factor 2 is relevant.",
    "confidence": 3
  }}
]

CRITICAL: Output ONLY the JSON array. Do not include any introductory text, explanations, or markdown formatting like ```json before or after the JSON array.
"""

# Refined prompt
CRITIQUE_PROMPT_TEMPLATE = """
Context:
Original Question: {question}

Your previous factors/justifications (formatted as JSON):
{previous_factors}

Other agents' most recent factors/justifications (formatted as JSON):
{other_agents_factors}

Human feedback (if any):
{human_feedback}

Instructions:
Based on all the context above:
1. Identify any high-impact factors currently missing from *your* list that others mentioned or that human feedback suggested.
2. Flag any factors in *your* current list that seem weak, incorrect, or redundant based on others' points or human feedback.
3. Revise *your* list of factors based on your critique.

Output your revised list as a JSON array, where each object represents a factor and has the following keys:
- "factor_name": A string containing the descriptive name of the factor.
- "justification": A string containing 1-2 sentences explaining the factor's relevance.
- "confidence": A number (integer or float) between 1 and 5 (inclusive), with 5 being the highest confidence.

Example format:
[
  {{
    "factor_name": "Revised Factor A",
    "justification": "Justification for revised factor A.",
    "confidence": 5
  }},
  {{
    "factor_name": "New Factor B",
    "justification": "Justification for new factor B based on critique.",
    "confidence": 4
  }}
]

CRITICAL: Output ONLY the JSON array. Do not include any introductory text, explanations, code block markers (like ```json), or summaries before or after the JSON array.
"""

# Note: This prompt is defined in core/merge_logic.py, not here.
# See core/merge_logic.py for the MERGE_FACTORS_PROMPT.

SUMMARIZATION_PROMPT_TEMPLATE = """
Consensus factors based on multi-agent debate:
{consensus_factors_details}

Supporting arguments and justifications from all agents:
{all_justifications}

Instructions:
Produce a concise, coherent final answer in prose, synthesizing the consensus factors and citing the strongest supporting arguments/evidence provided during the debate.
"""

JUDGE_PROMPT_TEMPLATE = """
Evaluate the quality of two answers to the question: "{question}"

Answer 1 (Baseline):
{baseline_answer}

Answer 2 (Merged from Debate):
{merged_answer}

Instructions:
Compare Answer 2 (Merged) against Answer 1 (Baseline) on the following dimensions. Rate each dimension as 'Better', 'Worse', or 'Equal'.

1. Completeness: Does the Merged answer cover more relevant factors or aspects than the Baseline?
   Rating: [Better/Worse/Equal]
   Reasoning: [Optional brief explanation]

2. Correctness: Does the Merged answer seem more accurate or factually sound than the Baseline? Are there any inaccuracies introduced?
   Rating: [Better/Worse/Equal]
   Reasoning: [Optional brief explanation]

3. Clarity: Is the Merged answer more clearly written and easier to understand than the Baseline?
   Rating: [Better/Worse/Equal]
   Reasoning: [Optional brief explanation]

Output only the ratings and optional reasoning in the format above.
"""

# --- V2 Prompts (Critique Prose Baseline) --- 

PROSE_BASELINE_GENERATION_TEMPLATE = """
Q: {question}

Please provide a comprehensive, well-reasoned answer to the question above. Structure your answer clearly.
"""

CRITIQUE_PROSE_BASELINE_TEMPLATE = """
Context:
Original Question: {question}

Provided Baseline Answer:
{prose_baseline}

Your Task:
1. Critically evaluate the Provided Baseline Answer in response to the Original Question.
2. Identify its key strengths and weaknesses. Consider completeness, correctness, potential biases, and missing perspectives.
3. Based on your critique, extract or formulate the most important factors (around 5-7) that should be considered for a comprehensive answer.

Output Format:
Format your extracted/formulated factors STRICTLY as a JSON array. Each object in the array must have the following keys:
- "factor_name": A string containing the descriptive name of the factor.
- "justification": A string containing 1-2 sentences explaining the factor's relevance *based on your critique of the baseline*. Mention how it addresses a strength, weakness, or omission.
- "confidence": A number (integer or float) between 1 and 5 (inclusive), reflecting your confidence in the factor's importance for answering the original question after considering the baseline.

Example:
[
  {{
    "factor_name": "Baseline Strength X",
    "justification": "The baseline correctly identified X, which is crucial because...",
    "confidence": 5
  }},
  {{
    "factor_name": "Missing Factor Y",
    "justification": "The baseline omitted Y, which is important for considering the aspect of...",
    "confidence": 4
  }}
]

CRITICAL: Output ONLY the JSON array. Do not include your critique text, introductory sentences, explanations, or markdown formatting like ```json before or after the JSON array.
"""

# Optional: Could be used for the anchor agent's self-critique, or reuse the main critique prompt.
# SELF_CRITIQUE_PROSE_BASELINE_TEMPLATE = CRITIQUE_PROSE_BASELINE_TEMPLATE 

# --- V2/V3 Merge Factors Prompt --- 
MERGE_FACTORS_PROMPT = """
You are an expert synthesis AI tasked with merging factors from a multi-agent debate.
You will be given a list of factors related to the question: "{question}"
Each factor includes a name, justification, confidence score (1-5), and the proposing agent.

Your Goal: Synthesize the collective insights into a concise, comprehensive, and ranked list of the *most important and distinct* factors, reflecting the nuances of the debate.

Your Task:
1.  **Analyze All Factors:** Carefully read all factors provided by the agents.
2.  **Identify Core Concepts:** Group factors discussing the same underlying concept, even with different wording. Pay attention to semantic meaning.
3.  **Synthesize Factors for Each Concept:** For each distinct conceptual group, create a *single*, representative factor.
    *   The synthesized `name` should be concise and accurately capture the core concept.
    *   The synthesized `justification` must summarize the key arguments, evidence, and nuances from the grouped factors. **Crucially, retain important specific examples or granular details mentioned in justifications if they add significant value or context.**
    *   The synthesized `confidence` score (float 1.0-5.0) must reflect the overall support (number of agents discussing the concept) and average certainty for the concept based on original confidences.
4.  **Ensure Breadth and Criticality:** When selecting concepts for synthesis, consider not only how frequently they were mentioned but also their *importance* to answering the original question. Ensure critical aspects (e.g., potential risks, financial considerations, regulatory impacts) are represented if discussed, even if only by one or two agents.
5.  **Rank Synthesized Factors:** Rank the final list of synthesized factors based on their overall importance, strength of support/confidence, and relevance to the original question.
6.  **Return Top K:** Return **only** the top {top_k} highest-ranked synthesized factors.

Output Format:
Output the result as a single, valid JSON list containing the synthesized factor objects. Each object in the list must have the keys "name", "justification", and "confidence".

CRITICAL: You MUST output ONLY the JSON list `[...]`. Ensure the JSON is strictly valid. Do NOT include any introductory text, explanations, summaries, or markdown formatting like ```json before or after the JSON list.

Factors from the debate:
{formatted_factors}

Please provide the top {top_k} synthesized factors in JSON list format:
"""

# --- V3 Refinement Prompt --- 
REFINE_PROMPT_TEMPLATE = """
You are an expert editor AI. You will be given an original baseline answer (prose) to a question, and a summary of key insights derived from a multi-agent debate on the same question.

Your task is to **integrate** the key insights from the debate summary into the original baseline answer to produce a refined, comprehensive final answer.

**Original Question:** {question}

**Original Baseline Answer:**
```
{baseline_prose}
```

**Key Insights from Debate Summary:**
```
{debate_summary}
```

**Instructions:**
1.  Thoroughly understand both the original baseline and the debate summary.
2.  Rewrite the baseline answer, incorporating the valid points, stronger arguments, specific examples, or refined perspectives mentioned in the debate summary.
3.  **Preserve the structure, scope, and level of detail** of the original baseline answer as much as possible. Do *not* simply replace the baseline with the summary.
4.  Ensure the final refined answer is coherent, well-structured, and addresses the original question comprehensively, benefiting from both the initial analysis and the debate's refinements.
5.  If the debate summary contradicts the baseline on a factual point, prioritize the likely correct information, potentially noting the discrepancy subtly if appropriate.

Output **only** the final refined prose answer. Do not include introductory phrases like "Here is the refined answer:".
"""

# Optional: Could be used for the anchor agent's self-critique, or reuse the main critique prompt.
# SELF_CRITIQUE_PROSE_BASELINE_TEMPLATE = CRITIQUE_PROSE_BASELINE_TEMPLATE 