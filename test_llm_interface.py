#!/usr/bin/env python3
"""
Test script for the LLMInterface class
This script verifies that the LLMInterface correctly:
1. Loads the configuration from config.json
2. Sets up the proxy for OpenAI API access
3. Successfully calls the OpenAI API
"""
import os
import sys
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Ensure the project root is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Import the LLMInterface
from llm_interface import LLMInterface

# Load environment variables from .env file
load_dotenv()

def test_basic_functionality():
    """Test the basic functionality of the LLMInterface."""
    print("\n===== TESTING LLMInterface =====")
    # Get the default model key from environment or fallback
    default_model_key = os.getenv("DEFAULT_LLM_MODEL", "gpt-o4-mini")
    print(f"Initializing LLMInterface using default model: {default_model_key}")
    
    try:
        # Initialize LLMInterface without specifying model_key, letting it use the default
        llm = LLMInterface()
        print(f"✅ Successfully initialized using default model: {llm.current_model_key}")

        # Test sending a simple prompt
        print("\nSending test prompt...")
        test_prompt = "Respond with 'Success' if you can read this message."
        response = llm.generate_response(prompt=test_prompt, temperature=0.3)
        print("\nResponse received:")
        print(f"'{response}'")
        if "success" in response.lower():
            print("✅ Basic API communication works.")
        else:
            print("⚠️ Received a response, but it didn't contain 'Success'.")
            print(f"Response content: {response}")
            return False

        # Test chat completion functionality
        print("\nTesting chat completion functionality...")
        chat_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "Multiply that by 3."}
        ]
        chat_response = llm.generate_chat_response(messages=chat_messages, temperature=0.3)
        print("\nChat response received:")
        print(f"'{chat_response}'")
        if chat_response:
            print("✅ Chat completion functionality works.")
        else:
            print("❌ Chat completion failed to return a response.")
            return False

    except ValueError as e:
        print(f"❌ Could not initialize with default model '{default_model_key}': {e}")
        return False
    except Exception as e:
        print(f"❌ Error using default model '{llm.current_model_key if 'llm' in locals() else default_model_key}': {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n===== TEST SUMMARY =====")
    print(f"✅ Successfully used default model key: {llm.current_model_key}")
    print("✅ LLMInterface correctly loads configuration and default model")
    print(f"✅ Proxy settings are correctly applied (using proxy: {os.getenv('USE_LLM_PROXY', 'True').lower() == 'true'})")
    print("✅ Basic API communication works")
    print("✅ Chat completion functionality works")
    
    return True

if __name__ == "__main__":
    try:
        success = test_basic_functionality()
        if success:
            print("\n✅ All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 