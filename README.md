# llmdebate2: CLI-Based Multi-LLM Debate System

## Overview
`llmdebate2` is a command-line proof-of-concept that orchestrates a structured debate protocol among multiple LLMs (O4-mini, Gemini 2.5, Grok 3). It:

- Fans out your question to each model in parallel
- Runs iterative debate rounds with optional human-in-the-loop feedback
- Merges consensus factors by endorsement and confidence
- Summarizes the final answer in prose
- Applies a judge agent quality guard with fallback to baseline
- Logs the full transcript for audit

## Prerequisites
- Python 3.10 or higher
- Unix-like shell (bash, zsh)

## Setup
1. Clone the repo and `cd` into the project root:
   ```bash
   git clone <repo-url> llmdebate2
   cd llmdebate2
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the example env file and fill in your API keys:
   ```bash
   cp .env.example .env
   # Edit .env to add your OPENAI_API_KEY, GEMINI_API_KEY, GROK_API_KEY, etc.
   ```

## Usage
Run the debate CLI:
```bash
python debate.py --max-rounds 3 --top-k 5 [--verbose] [--output transcript.json]
```
- `--max-rounds`: Maximum debate iterations (default: 3)
- `--top-k`: Number of factors to include in final merge (default: 5)
- `--verbose`: Enable debug & verbose logging
- `--output`: Path to write JSON transcript (default: `transcript.json`)

### Sample Session
```bash
$ python debate.py --max-rounds 2 --top-k 5
Question: What drives EV market success?

[Baseline] O4-mini: Battery tech, Charging network, Cost incentives...

[Round 1]
Agent O4-mini: Revised factors...
Agent Gemini: Revised factors...
Agent Grok: Revised factors...
Feedback: Please consider policy impacts.

[Merge] Consensus: Charging, Battery, Policy
[Summarizer] Final Answer: ...
[Judge] Baseline: Pass, Merged: Pass → Accept
``` 

## Development
- Use a Python virtual environment (`venv`) for isolation
- All LLM access must go through `src/core/llm_interface.py`
- Follow the task checklist in `tasklist.md`

## Documentation
- **PRD**: `prd.md`  
- **Implementation Plan**: `implementation_plan.md`  
- **Task List**: `tasklist.md`  
- **File Structure**: `filestructure.md`  
- **Tech Stack**: `techstack.md`  

## Testing
Run unit and smoke tests via `pytest`:
```bash
pytest
```

## License
This project is released under the MIT License. See `LICENSE` for details. 