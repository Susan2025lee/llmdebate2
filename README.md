# Multi-LLM Debate System

This project implements a system where multiple Large Language Models (LLMs) engage in a structured debate to answer a user's question. It explores different debate formats across several versions (V1, V2, V3, V4) and includes both Command-Line Interface (CLI) and a Web User Interface (Web UI) for interaction.

## Versions

*   **V1 (`debate.py`):** Factor-centric debate. Agents generate lists of factors, critique them, merge them, and a final answer is summarized.
*   **V2 (`debate_v2.py`):** Introduces a prose baseline answer generated first, followed by a V1-style factor debate to refine it.
*   **V3 (`debate_v3.py`):** Integrates the debate summary more directly into refining the initial prose baseline.
*   **V4 (`debate_v4.py`):** Focuses on maximizing perspective diversity. Generates parallel prose baselines from multiple agents, followed by a free-form critique round where agents critique each other's full prose answers. Offers two synthesis methods:
    *   **V4 Default Synthesizer:** Synthesizes the final answer based on *all* initial baselines and *all* critique texts.
    *   **V3 Refine Style Synthesizer:** Integrates the critique texts into *only* the baseline generated by the reference agent (currently O4-mini), similar to the V3 refinement process.

Detailed agent interactions and prompts for each version are documented in `agent_interaction.md`.

## Features

*   Supports multiple debate versions (V1-V4).
*   Integrates with multiple LLMs (OpenAI O4-mini, Google Gemini-2.5, optional Grok-3) via `LLMInterface`.
*   Provides both CLI and Web UI interfaces.
*   Web UI uses Flask and Socket.IO for real-time progress updates.
*   Includes a Judge Agent to evaluate the quality of the final answer against the baseline (in V3/V4).
*   V4 allows selecting the synthesis method via the Web UI.
*   Transcript generation for debate analysis.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```
2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate 
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure API Keys:**
    *   Create a `.env` file in the project root.
    *   Add your API keys:
        ```dotenv
        # Required
        OPENAI_API_KEY=your_openai_api_key
        GOOGLE_API_KEY=your_google_api_key 
        
        # Optional
        # GROK_API_KEY=your_grok_api_key 
        
        # Optional: Proxy if needed for OpenAI
        # OPENAI_PROXY_URL=http://your_proxy_url
        ```

## Usage

### Command Line Interface (CLI)

You can run debates directly from the command line for each version:

```bash
# V1
python debate.py -q "Your question here?" -o transcript_v1.json

# V2
python debate_v2.py -q "Your question here?" -o transcript_v2.json

# V3
python debate_v3.py -q "Your question here?" -o transcript_v3.json

# V4 (Defaults to 1 round, V4 Synthesizer)
python debate_v4.py -q "Your question here?" -o transcript_v4.json 
```

Use the `-h` flag for more options (e.g., `-m` for max rounds in V4).

### Web User Interface (Web UI)

1.  **Start the Flask server:**
    ```bash
    python app.py
    ```
    *(Or use `flask run` if configured)*

2.  **Open your browser:** Navigate to `http://127.0.0.1:5000` (or the host/port specified).

3.  **Use the Interface:**
    *   Enter your question.
    *   Select the Debate Version (V3 or V4).
    *   If V4 is selected, choose the desired Synthesizer Type.
    *   Click "Start Debate".
    *   Progress and results will be displayed in real-time.

## Documentation

*   `agent_interaction.md`: Details the workflow, agent interactions, and prompts for each version.
*   `tasklist.md`: Tracks the implementation progress.

## Contributing

(Add contribution guidelines if applicable)

## License

(Add license information if applicable) 