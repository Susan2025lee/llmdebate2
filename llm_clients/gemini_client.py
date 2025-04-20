import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure the Gemini client from environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-pro") # Default to gemini-pro if not set

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found in .env. Gemini client will not function.")
    # Define a dummy client or raise an error if preferred
    genai_model = None 
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # Initialize the specific model
    genai_model = genai.GenerativeModel(GEMINI_MODEL_NAME)

async def query_gemini(prompt: str, temperature: float = 0.7, max_tokens: int = 2000) -> str:
    """
    Query the configured Gemini model directly using the google-generativeai SDK.
    Reads API key and model name from .env variables.
    Returns the raw text response.
    """
    if not genai_model:
        return "Error: Gemini client not configured. Check GEMINI_API_KEY in .env."

    try:
        # Use run_async for non-blocking call if available, otherwise wrap sync call
        # Note: google-generativeai SDK might have different async patterns.
        # This example uses generate_content which might be synchronous.
        # We wrap it in to_thread for safety in an async context.
        
        # Define generation config
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            # max_output_tokens=max_tokens # Uncomment if API supports this directly
        )
        
        # Wrap the synchronous call in asyncio.to_thread
        response = await asyncio.to_thread(
            genai_model.generate_content, 
            prompt,
            generation_config=generation_config
        )
        
        # Check for response content; structure may vary based on model/version
        if response and hasattr(response, 'text'):
            return response.text
        else:
            # Log or handle cases where response might be empty or structured differently
            print(f"Warning: Unexpected Gemini response format: {response}")
            return "Error: Received unexpected response from Gemini."

    except Exception as e:
        print(f"Error querying Gemini: {e}")
        # Consider more specific error handling based on google-generativeai exceptions
        return f"Error: Failed to get response from Gemini. {e}" 