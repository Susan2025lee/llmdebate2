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

# Note: This critique prompt needs context injected dynamically
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
2. Flag any factors in *your* current list that seem weak, incorrect, or redundant based on others' points or human feedback. Provide brief reasons for flagging (mentally, no need to output this critique).
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