# File Structure: CLI-Based Multi-LLM Debate System

```
llmdebate2/
├── app.py                  # Flask web application entry point
├── debate.py               # Main entry point (V1: JSON Baseline)
├── debate_v2.py            # Main entry point (V2: Critique Prose Baseline)
├── debate_v3.py            # Main entry point (V3: Integrated Refinement)
├── llm_clients/
│   ├── __init__.py
│   ├── o4_client.py        # Wrapper for O4-mini
│   ├── gemini_client.py    # Wrapper for Gemini 2.5
│   └── grok_client.py      # Wrapper for Grok 3
├── core/
│   ├── __init__.py
│   ├── llm_interface.py    # Central LLMInterface for all model access
│   ├── debate_engine.py    # Orchestrates debate rounds
│   ├── merge_logic.py      # Endorsement & confidence logic + V3 Refinement
│   └── summarizer.py       # Final answer synthesizer
├── judge/
│   ├── __init__.py
│   └── judge_agent.py      # Quality-guard logic
├── utils/
│   ├── __init__.py
│   ├── prompts.py          # Prompt templates (incl. V2/V3 specific ones)
│   └── models.py           # Data classes (Factor, AgentResponse)
├── templates/
│   └── index.html          # HTML template for Flask app
├── tests/
│   └── test_debate_flow.py # Smoke tests (and others...)
├── requirements.txt        # Dependency lock
├── README.md               # Project overview and setup
└── .env                    # API keys (gitignored)
``` 