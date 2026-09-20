"""
Direct test of OpenRouter API with fresh .env loading
"""
from pathlib import Path
from dotenv import load_dotenv
import os

# Force reload .env
env_path = Path(__file__).parent.parent / '.env'
print(f"Loading .env from: {env_path}")
print(f"File exists: {env_path.exists()}")

load_dotenv(dotenv_path=env_path, override=True)

# Check what we got
api_key = os.getenv('OPENROUTER_API_KEY')
model = os.getenv('OPENROUTER_MODEL', 'openai/gpt-3.5-turbo')

print(f"\nAPI Key loaded: {api_key[:30] if api_key else 'NONE'}...")
print(f"Model: {model}")

if not api_key:
    print("\n❌ No API key found in environment!")
    exit(1)

# Now test the API
print("\n" + "="*60)
print("Testing OpenRouter API with loaded key...")
print("="*60)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.shared_libs.simple_openrouter import SimpleOpenRouterClient

# Create client with explicit API key
client = SimpleOpenRouterClient(api_key=api_key, model=model, test_on_init=True)

if client.api_working:
    print("\n✅ SUCCESS! API is working!")
    print(f"   Model: {client.model}")
    
    # Test a simple request
    print("\nTesting chat completion...")
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Say 'Hello from FL-DDoS!' in exactly 5 words"}],
        max_tokens=20
    )
    print(f"   Response: {response}")
    
else:
    print("\n❌ API test failed - check the error above")
    print("   The system will fall back to MOCK mode")

print("\n" + "="*60)
