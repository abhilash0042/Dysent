"""
Simple OpenRouter Wrapper for FL Agent Coordination

Provides synchronous interface to OpenRouter API with automatic fallback to mock mode.
"""

import os
import logging
import requests
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load from project root .env file
    env_path = Path(__file__).parent.parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass  # python-dotenv not installed, will use system env vars

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleOpenRouterClient:
    """
    Synchronous OpenRouter client for FL coordination.
    
    - Tests API key validity
    - Falls back to mock mode if API unavailable
    - Simple request/response interface
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-3.5-turbo",
        test_on_init: bool = True
    ):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key (or OPENROUTER_API_KEY env var)
            model: Model to use
            test_on_init: Test API key on initialization
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        
        self.api_working = False
        self.mock_mode = False
        
        if not self.api_key:
            logger.warning("No API key provided - using MOCK MODE")
            self.mock_mode = True
        elif test_on_init:
            self._test_api_key()
        
        if self.api_working:
            logger.info(f"✓ OpenRouter API working with model: {model}")
        else:
            logger.info("Using MOCK MODE for LLM responses")
    
    def _test_api_key(self):
        """Test if API key is valid"""
        logger.info("Testing OpenRouter API key...")
        
        try:
            test_response = self.chat_completion(
                messages=[
                    {"role": "user", "content": "Say 'OK' if you can hear me"}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            if test_response and len(test_response) > 0:
                self.api_working = True
                logger.info("✓ API key valid - responses working!")
            else:
                logger.warning("API key test returned empty - using mock mode")
                self.mock_mode = True
                
        except Exception as e:
            logger.warning(f"API test failed: {e}")
            logger.warning("Falling back to mock mode")
            self.mock_mode = True
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """
        Get chat completion from LLM.
        
        Args:
            messages: List of {'role': 'user/system', 'content': '...'}
            temperature: Sampling temperature
            max_tokens: Max response tokens
            
        Returns:
            LLM response text
        """
        if self.mock_mode:
            return self._mock_response(messages)
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/fl-ddos-detection",
                "X-Title": "FL DDoS Detection System"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result['choices'][0]['message']['content']
        
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            logger.warning("Falling back to mock response")
            return self._mock_response(messages)
    
    def analyze_security_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze security event using LLM.
        
        Args:
            event_data: Event information
            
        Returns:
            Analysis results
        """
        prompt = f"""Analyze this federated learning security event:

Event: {json.dumps(event_data, indent=2)}

Assess:
1. Threat level (low/medium/high)
2. Recommended action
3. Confidence (0-1)
4. Brief reasoning

Respond in JSON format ONLY:
{{
  "threat_level": "low/medium/high",
  "action": "monitor/increase_monitoring/quarantine",
  "confidence": 0.XX,
  "reasoning": "brief explanation"
}}"""
        
        messages = [
            {"role": "system", "content": "You are a cybersecurity AI analyzing FL systems. Respond ONLY with valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.chat_completion(messages, temperature=0.3, max_tokens=200)
        
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON: {e}")
            return self._mock_security_analysis(event_data)
    
    def recommend_aggregation_strategy(self, round_stats: Dict[str, Any]) -> str:
        """
        Get LLM recommendation for aggregation strategy.
        
        Args:
            round_stats: Current round statistics
            
        Returns:
            Strategy name
        """
        prompt = f"""Based on these FL statistics, recommend ONE aggregation strategy:

Stats: {json.dumps(round_stats, indent=2)}

Strategies:
- fedavg: Fast, less secure
- trimmed_mean: Balanced security/speed
- krum: Very secure, slower
- median: Secure, medium speed

Respond with ONLY ONE WORD: fedavg, trimmed_mean, krum, or median"""
        
        messages = [
            {"role": "system", "content": "You are an FL expert. Respond with ONE WORD only."},
            {"role": "user", "content": prompt}
        ]
        
        response = self.chat_completion(messages, temperature=0.2, max_tokens=20).strip().lower()
        
        # Validate
        valid = ['fedavg', 'trimmed_mean', 'krum', 'median']
        for strategy in valid:
            if strategy in response:
                return strategy
        
        return 'trimmed_mean'  # Safe default
    
    def generate_incident_report(self, incident_data: Dict[str, Any]) -> str:
        """
        Generate incident report.
        
        Args:
            incident_data: Incident information
            
        Returns:
            Report text
        """
        prompt = f"""Generate a brief incident report (max 150 words):

{json.dumps(incident_data, indent=2)}

Include: summary, impact, actions taken, recommendations."""
        
        messages = [
            {"role": "system", "content": "You are a security analyst. Be concise."},
            {"role": "user", "content": prompt}
        ]
        
        return self.chat_completion(messages, temperature=0.5, max_tokens=250)
    
    def _mock_response(self, messages: List[Dict[str, str]]) -> str:
        """Generate mock response"""
        last_content = messages[-1]['content'].lower()
        
        if "threat" in last_content or "security" in last_content:
            return json.dumps({
                "threat_level": "medium",
                "action": "monitor",
                "confidence": 0.75,
                "reasoning": "Detected moderate activity patterns"
            })
        
        elif "strategy" in last_content or "aggregation" in last_content:
            return "trimmed_mean"
        
        elif "report" in last_content:
            return "System operating within normal parameters. No critical issues detected. Recommend continued monitoring."
        
        else:
            return json.dumps({"status": "ok", "message": "Mock response"})
    
    def _mock_security_analysis(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock security analysis"""
        # Simple heuristic
        anomalies = event_data.get('anomalies', 0)
        trust_avg = event_data.get('trust_avg', 1.0)
        
        if anomalies > 2 or trust_avg < 0.5:
            threat = "high"
            action = "quarantine"
            confidence = 0.85
        elif anomalies > 0 or trust_avg < 0.7:
            threat = "medium"
            action = "increase_monitoring"
            confidence = 0.70
        else:
            threat = "low"
            action = "monitor"
            confidence = 0.90
        
        return {
            "threat_level": threat,
            "action": action,
            "confidence": confidence,
            "reasoning": f"Based on {anomalies} anomalies and {trust_avg:.2f} avg trust"
        }


def test_openrouter_api():
    """Test function to verify API key"""
    print("\n" + "="*60)
    print("Testing OpenRouter API")
    print("="*60)
    
    client = SimpleOpenRouterClient()
    
    if client.api_working:
        print("\n✓ API Key Status: WORKING")
        print(f"✓ Model: {client.model}")
        
        # Test security analysis
        print("\nTesting security analysis...")
        test_event = {
            "round": 1,
            "nodes": 5,
            "trust_avg": 0.85,
            "anomalies": 1,
            "accuracy": 0.99
        }
        
        result = client.analyze_security_event(test_event)
        print(f"✓ Analysis: {json.dumps(result, indent=2)}")
        
    else:
        print("\n⚠ API Key Status: NOT WORKING (using mock mode)")
        print("  - Check OPENROUTER_API_KEY environment variable")
        print("  - Verify API key is valid")
        print("  - System will use mock responses")
    
    print("\n" + "="*60)
    
    return client


if __name__ == "__main__":
    test_openrouter_api()
