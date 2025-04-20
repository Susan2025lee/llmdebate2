# File Structure: CLI-Based Multi-LLM Debate System

```
llmdebate2/
├── debate.py               # Main entry point
├── llm_clients/
│   ├── __init__.py
│   ├── o4_client.py        # Wrapper for O4-mini
│   ├── gemini_client.py    # Wrapper for Gemini 2.5
│   └── grok_client.py      # Wrapper for Grok 3
├── core/
│   ├── __init__.py
│   ├── llm_interface.py       # Central LLMInterface for all model access
│   ├── debate_engine.py     # Orchestrates debate rounds
│   ├── merge_logic.py       # Endorsement & confidence logic
│   └── summarizer.py        # Final answer synthesizer
├── judge/
│   ├── __init__.py
│   └── judge_agent.py       # Quality-guard logic
├── utils/
│   ├── __init__.py
│   ├── prompts.py           # Prompt templates
│   └── models.py            # Data classes (Factor, AgentResult)
├── tests/
│   └── test_debate_flow.py  # Smoke tests
├── requirements.txt         # Dependency lock
├── README.md                # Project overview and setup
└── .env                     # API keys (gitignored)
``` 