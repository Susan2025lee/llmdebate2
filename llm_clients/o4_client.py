import os
import asyncio
from llm_interface import LLMInterface

# Initialize LLMInterface for O4-mini (default from env or fallback)
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gpt-o4-mini")
llm_o4 = LLMInterface(model_key=DEFAULT_MODEL)

async def query_o4(prompt: str) -> str:
    """
    Query the O4-mini model for a given prompt and return the raw text response.
    """
    # Run blocking generate_response in thread pool
    response = await asyncio.to_thread(llm_o4.generate_response, prompt)
    return response 