# File Structure: CLI-Based Multi-LLM Debate System

```
llmdebate2/
├── app.py                  # Flask web application entry point
├── debate.py               # Main entry point (V1: JSON Baseline)
├── debate_v2.py            # Main entry point (V2: Critique Prose Baseline)
├── debate_v3.py            # Main entry point (V3: Integrated Refinement)
├── debate_v4.py            # Main entry point (V4: Free-Form Debate - Planned)
├── llm_clients/
│   ├── __init__.py
│   ├── o4_client.py        # Wrapper for O4-mini
│   ├── gemini_client.py    # Wrapper for Gemini 2.5
│   └── grok_client.py      # Wrapper for Grok 3
├── core/
│   ├── __init__.py
│   ├── llm_interface.py    # Central LLMInterface for all model access
│   ├── debate_engine.py    # Orchestrates debate rounds (V1-V3)
│   ├── debate_engine_v4.py # Orchestrates free-form debate rounds (V4 - Planned)
│   ├── merge_logic.py      # V1-V3 Factor merging + V3 Refinement
│   ├── synthesizer.py      # V4 Final answer synthesis (Planned)
│   └── summarizer.py       # V1-V3 Final answer synthesizer from factors
├── judge/
│   ├── __init__.py
│   └── judge_agent.py      # Quality-guard logic (May need V4 adaptation)
├── utils/
│   ├── __init__.py
│   ├── prompts.py          # Prompt templates (Incl. V2/V3/V4 specific ones)
│   └── models.py           # Data classes (Factor, AgentResponse - Less used in V4)
├── templates/
│   └── index.html          # HTML template for Flask app (Needs V4 updates)
├── tests/
│   └── test_debate_flow.py # Smoke tests (and others...)
├── requirements.txt        # Dependency lock
├── README.md               # Project overview and setup
└── .env                    # API keys (gitignored)
```