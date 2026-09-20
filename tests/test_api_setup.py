"""
Quick script to test OpenRouter API and enable real LLM mode
Run this after setting OPENROUTER_API_KEY environment variable
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("\n" + "="*70)
print("OpenRouter API Configuration Check")
print("="*70 + "\n")

# Check environment variable
api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("❌ API Key Status: NOT SET\n")
    print("To enable real LLM responses:")
    print("\n1. Get API key from: https://openrouter.ai")
    print("\n2. Set environment variable:")
    print("\n   PowerShell:")
    print('   $env:OPENROUTER_API_KEY = "sk-or-v1-YOUR_API_KEY"')
    print("\n   WSL/Linux:")
    print('   export OPENROUTER_API_KEY="sk-or-v1-YOUR_API_KEY"')
    print("\n3. Re-run this script to verify")
    print("\n" + "="*70 + "\n")
    sys.exit(0)

print(f"✓ API Key Status: SET")
print(f"  Key: {api_key[:20]}...")

# Test API
print("\nTesting OpenRouter API connection...")

from projects.shared_libs.simple_openrouter import SimpleOpenRouterClient

client = SimpleOpenRouterClient(api_key=api_key, test_on_init=True)

if client.api_working:
    print("\n✅ SUCCESS: Real API Mode Enabled!")
    print(f"  Model: {client.model}")
    
    # Quick test
    print("\nQuick Security Analysis Test...")
    test_event = {
        "round": 1,
        "nodes": 5,
        "trust_avg": 0.85,
        "anomalies": 1
    }
    
    result = client.analyze_security_event(test_event)
    print(f"  Threat Level: {result.get('threat_level')}")
    print(f"  Action: {result.get('action')}")
    print(f"  Reasoning: {result.get('reasoning')}")
    
    print("\n✓ Real LLM responses are now active!")
    
else:
    print("\n⚠ API Key set but connection failed")
    print("  Check:")
    print("  - API key is valid on OpenRouter dashboard")
    print("  - Internet connection is working")
    print("  - No firewall blocking openrouter.ai")
    print("\n  System will use MOCK mode as fallback")

print("\n" + "="*70 + "\n")
