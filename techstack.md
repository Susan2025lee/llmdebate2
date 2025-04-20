# Tech Stack: CLI-Based Multi-LLM Debate System

| Component         | Choice & Rationale                                              |
|-------------------|----------------------------------------------------------------|
| Language          | Python 3.10+ (asyncio support, rich ecosystem)                  |
| CLI Framework     | Typing with `typer` (easy flags, help text, Pythonic)          |
| LLM SDKs          | `openai` for O4-mini; Google PaLM SDK for Gemini 2.5; custom Grok client | Compact, official APIs for each LLM.
| Concurrency       | `asyncio`, `asyncio.gather` for parallel calls                 |
| Prompts & I/O     | In-code templates; built-in `print`/`input`                     |
| Summarization     | Reuse one LLM as summarizer                                    |
| Quality Guard     | Judge agent on O4-mini or higher-tier model                    |
| Logging           | Python `logging` + JSON export                                  |
| Config & Env      | `python-dotenv` for `.env` loading; `typer` flags               |
| Development Env   | Use Python virtual environment (`venv`) for dependency isolation |
| Output Styling    | `rich` for colored text and spinners                            |
| Testing           | `pytest` for unit and smoke tests                              |
| LLM Access        | All LLM calls go through `LLMInterface` (`src/core/llm_interface.py`) to handle proxy configuration and model-specific adaptations |
| Factor Merging    | (Planned) Add `sentence-transformers` for semantic clustering   |
``` 