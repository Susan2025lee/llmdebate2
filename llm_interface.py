import os
import sys
import json
from typing import Dict, List, Optional, Any, Union
from openai import OpenAI
from dotenv import load_dotenv  # Import load_dotenv

# Add the project root to the Python path if needed
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import ModelManager from project root
from model_manager import ModelManager

# Load environment variables from .env file
load_dotenv()

class LLMInterface:
    """
    Interface for interacting with LLMs, specifically configured for OpenAI models
    with optional proxy settings.
    
    This class handles ONLY the communication with LLM APIs, providing a consistent
    interface regardless of the underlying model being used.
    
    Key features:
    - Conditionally applies proxy settings based on USE_LLM_PROXY environment variable.
    - Automatically detects and adapts to model-specific limitations
    - Converts system messages to user messages for models that don't support system roles
    - Handles temperature restrictions for models with fixed temperature requirements
    - Provides a consistent API across different OpenAI models
    """
    
    # OpenAI proxy configuration (used if USE_LLM_PROXY is True)
    OPENAI_PROXY = {
        "http": "http://testai:testai@192.168.1.7:6666",
        "https": "http://testai:testai@192.168.1.7:6666"
    }
    
    # Models with specific limitations
    MODELS_WITHOUT_SYSTEM_ROLE = ["o1-mini", "gpt-o1-mini"]
    MODELS_WITH_FIXED_TEMPERATURE = ["o1-mini", "gpt-o1-mini", "o3-mini", "gpt-o3-mini", "o4-mini"]
    
    def __init__(self, config_path: Optional[str] = None, model_key: Optional[str] = None):
        """
        Initialize the LLM interface with specified configuration and conditional proxy.
        
        Args:
            config_path: Path to the config.json file, if None will use default location
            model_key: The model key to use from config.json. If None, uses DEFAULT_LLM_MODEL from env or falls back to "gpt-o4-mini".
        """
        # Determine model key from parameter or environment default
        default_key = os.getenv("DEFAULT_LLM_MODEL", "gpt-o4-mini")
        self.current_model_key = model_key or default_key

        # Initialize ModelManager to access configuration
        self.model_manager = ModelManager(config_path)
        
        # Select the model to use
        self.current_model_config = self.model_manager.get_model_config(self.current_model_key)
        
        if not self.current_model_config:
            available_models = list(self.model_manager.available_models.keys())
            raise ValueError(f"Model '{self.current_model_key}' not found in configuration. Available models: {available_models}")
            
        # Determine provider and initialize the appropriate client
        provider = self.current_model_config.get("provider")
        if provider == "openai":
            # --- Conditional Proxy Setup for OpenAI ---
            use_proxy_str = os.getenv('USE_LLM_PROXY', 'True').lower()
            print(f"[DEBUG] Raw USE_LLM_PROXY: '{os.getenv('USE_LLM_PROXY')}' -> '{use_proxy_str}'")
            use_proxy = use_proxy_str == 'true'
            print(f"[DEBUG] Using proxy: {use_proxy}")
            if use_proxy:
                print("Configuring OpenAI client to use proxy...")
                os.environ["HTTP_PROXY"] = self.OPENAI_PROXY["http"]
                os.environ["HTTPS_PROXY"] = self.OPENAI_PROXY["https"]
            else:
                print("Configuring OpenAI client WITHOUT proxy...")
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
            self.client = OpenAI(api_key=self.current_model_config["api_key"])
            self.model_name = self.current_model_config["config"]["name"]
            print(f"LLMInterface initialized (OpenAI) with model: {self.model_name}")
            # Set model limitation flags
            self.supports_system_role = self.model_name not in self.MODELS_WITHOUT_SYSTEM_ROLE
            self.has_fixed_temperature = self.model_name in self.MODELS_WITH_FIXED_TEMPERATURE
            self.provider = "openai"
        elif provider == "gemini":
            # Attempt to initialize Google PaLM (Gemini) client
            try:
                print("Configuring Gemini (PaLM) client...")
                import google.generativeai as palm
                gemini_key = self.current_model_config.get("api_key") or os.getenv("GEMINI_API_KEY")
                if not gemini_key:
                    raise ValueError("GEMINI_API_KEY environment variable is required for Gemini provider")
                palm.configure(api_key=gemini_key)
                self.client = palm
                self.model_name = self.current_model_config["config"]["model_name"]
                print(f"LLMInterface initialized (Gemini) with model: {self.model_name}")
                self.supports_system_role = True
                self.has_fixed_temperature = False
                self.provider = "gemini"
            except ImportError:
                # Fallback to OpenAI if Gemini client library not available
                print("Google generative AI library not found; falling back to OpenAI for Gemini provider.")
                # Reuse OpenAI client initialization logic
                use_proxy_str = os.getenv('USE_LLM_PROXY', 'True').lower()
                use_proxy = use_proxy_str == 'true'
                if use_proxy:
                    os.environ["HTTP_PROXY"] = self.OPENAI_PROXY["http"]
                    os.environ["HTTPS_PROXY"] = self.OPENAI_PROXY["https"]
                else:
                    os.environ.pop("HTTP_PROXY", None)
                    os.environ.pop("HTTPS_PROXY", None)
                self.client = OpenAI(api_key=self.current_model_config.get("api_key") or os.getenv("OPENAI_API_KEY"))
                # Use default LLM model for fallback
                fallback_model = os.getenv("DEFAULT_LLM_MODEL", "gpt-o4-mini")
                self.model_name = self.model_manager.get_model_config(fallback_model)["config"]["name"]
                print(f"LLMInterface initialized (fallback OpenAI) with model: {self.model_name}")
                self.supports_system_role = self.model_name not in self.MODELS_WITHOUT_SYSTEM_ROLE
                self.has_fixed_temperature = self.model_name in self.MODELS_WITH_FIXED_TEMPERATURE
                self.provider = "openai"
        else:
            raise ValueError(f"Provider '{provider}' not supported by LLMInterface.")

    def generate_response(self, prompt: str, system_prompt: Optional[str] = None, 
                         temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
        """
        Generate a response from the LLM using a simple prompt.
        
        For models that don't support system roles (like gpt-o1-mini), the system_prompt
        will be automatically converted and prepended to the user prompt.
        
        Args:
            prompt: The user's prompt to send to the model
            system_prompt: Optional system message to guide the model's behavior
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
                         Note: Some models only support the default temperature of 1.0
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            The model's response as a string
        """
        messages = []
        
        if system_prompt:
            if self.supports_system_role:
                messages.append({"role": "system", "content": system_prompt})
            else:
                # For models that don't support system roles, prepend to user message
                prompt = f"[System instruction: {system_prompt}]\n\n{prompt}"
        
        messages.append({"role": "user", "content": prompt})
        
        return self.generate_chat_response(messages, temperature, max_tokens)
    
    def generate_chat_response(self, messages: List[Dict[str, str]], 
                              temperature: float = 0.7, 
                              max_tokens: Optional[int] = None) -> str:
        """
        Generate a response from the LLM using a conversation history.
        
        This method automatically adapts messages and parameters based on model limitations:
        - For models without system role support, system messages are converted to user messages
        - For models with fixed temperature, the temperature parameter is omitted
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
                         Note: Some models only support the default temperature of 1.0
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            The model's response as a string
        """
        try:
            # For models without system role support, convert system messages to user messages
            if not self.supports_system_role:
                converted_messages = []
                system_instructions = []
                
                for msg in messages:
                    if msg["role"] == "system":
                        system_instructions.append(msg["content"])
                    else:
                        converted_messages.append(msg)
                
                # If there were system messages, prepend them to the first user message
                if system_instructions and converted_messages:
                    for i, msg in enumerate(converted_messages):
                        if msg["role"] == "user":
                            system_text = "\n\n".join(system_instructions)
                            converted_messages[i]["content"] = f"[System instructions: {system_text}]\n\n{msg['content']}"
                            break
                
                messages = converted_messages
            
            # Prepare the request parameters
            params: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages
            }
            
            # Add temperature only for models that support it
            if not self.has_fixed_temperature:
                params["temperature"] = temperature
            
            # Add max_tokens if specified
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            
            # Dispatch request based on provider set at init
            provider = getattr(self, 'provider', self.current_model_config.get("provider"))
            if provider == "openai":
                print(f"Sending request to OpenAI model {self.model_name}...")
                response = self.client.chat.completions.create(**params)
                return response.choices[0].message.content
            else:
                # For any other provider (e.g., gemini fallback to openai)
                print(f"Fallback: sending request to model {self.model_name} via OpenAI client...")
                response = self.client.chat.completions.create(**params)
                return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error generating response: {e}")
            raise

    def close(self):
        """
        Clean up resources when done with the interface.
        """
        # Current OpenAI client doesn't require explicit cleanup,
        # but including this method for future-proofing and consistency
        # with the resource management pattern
        pass


# Example usage
if __name__ == "__main__":
    try:
        # Initialize the interface
        llm = LLMInterface()
        
        # Test a simple prompt
        response = llm.generate_response(
            prompt="Hello, can you hear me?",
            temperature=0.7
        )
        print("\nResponse to test prompt:")
        print(response)
        
    except Exception as e:
        print(f"Error in example usage: {e}")
        import traceback
        traceback.print_exc() 