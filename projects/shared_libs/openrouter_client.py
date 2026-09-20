"""
OpenRouter API Client for LLM-Based Agent Intelligence

Provides interface to OpenRouter API for intelligent agent decision-making
in DDoS detection and response scenarios.
"""

import os
import httpx
import asyncio
from typing import Dict, List, Optional, Any
import logging
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API"""
    
    DEFAULT_MODEL = "openai/gpt-4-turbo"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize OpenRouter client
        
        Args:
            api_key: OpenRouter API key (or uses OPENROUTER_API_KEY env var)
            model: Model to use (or uses OPENROUTER_MODEL env var)
            base_url: API base URL
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model or os.getenv("OPENROUTER_MODEL", self.DEFAULT_MODEL)
        self.base_url = base_url or os.getenv("OPENROUTER_BASE_URL", self.DEFAULT_BASE_URL)
        self.timeout = timeout
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
        logger.info(f"Initialized OpenRouter client with model: {self.model}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get chat completion from OpenRouter
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            Response dictionary
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        payload.update(kwargs)
        
        try:
            response = await self.client.post(
                "/chat/completions",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            raise
    
    async def get_agent_decision(
        self,
        system_prompt: str,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3  # Lower for more deterministic security decisions
    ) -> str:
        """
        Get agent decision from LLM
        
        Args:
            system_prompt: System prompt defining agent role
            user_query: User query/situation
            context: Additional context dictionary
            temperature: Sampling temperature
            
        Returns:
            Agent's response
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add context if provided
        if context:
            context_str = "\n\nCurrent Context:\n" + json.dumps(context, indent=2)
            user_query += context_str
        
        messages.append({"role": "user", "content": user_query})
        
        response = await self.chat_completion(
            messages=messages,
            temperature=temperature
        )
        
        # Extract response text
        return response['choices'][0]['message']['content']
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def __del__(self):
        """Cleanup"""
        try:
            asyncio.create_task(self.close())
        except:
            pass


class DDoSAgentPrompts:
    """Prompt templates for DDoS detection agents"""
    
    DETECTION_AGENT_SYSTEM = """You are an expert DDoS detection agent in a federated learning network security system. 
    
Your role is to:
1. Analyze network traffic patterns and model predictions
2. Assess the severity and type of potential DDoS attacks
3. Make decisions on alert generation and response actions
4. Coordinate with other agents in the network

You have access to:
- Real-time traffic features (packet rates, byte volumes, flag counts, etc.)
- Local model predictions and confidence scores
- Historical attack patterns
- Trust scores of other nodes

Respond with clear, actionable decisions in JSON format."""

    COORDINATION_AGENT_SYSTEM = """You are a coordination agent in a distributed DDoS defense system.

Your role is to:
1. Process alerts from multiple detection nodes
2. Assess overall threat level across the network
3. Recommend coordinated mitigation strategies
4. Manage trust scores and node reputation
5. Identify potential Byzantine/malicious nodes

Consider:
- Spatial and temporal correlation of attacks
- Node trust scores and historical behavior
- Resource constraints and effectiveness trade-offs

Provide structured recommendations for system-wide defense."""

    TRUST_ASSESSMENT_SYSTEM = """You are a zero-trust security assessment agent.

Your role is to:
1. Evaluate the trustworthiness of federated learning nodes
2. Detect anomalous model updates that may indicate poisoning
3. Assess model update quality and consistency
4. Recommend quarantine or acceptance decisions

You analyze:
- Model weight statistics (mean, variance, distribution)
- Historical node performance
- Deviation from expected update patterns
- Correlation with known attack signatures

Provide trust score updates and security recommendations."""

    @staticmethod
    def format_detection_query(
        traffic_features: Dict[str, float],
        model_prediction: str,
        confidence: float,
        historical_context: Optional[Dict] = None
    ) -> str:
        """Format query for detection agent"""
        query = f"""Traffic Pattern Analysis Request:

CURRENT TRAFFIC FEATURES:
{json.dumps(traffic_features, indent=2)}

MODEL PREDICTION: {model_prediction}
CONFIDENCE: {confidence:.2%}

{'HISTORICAL CONTEXT:' + chr(10) + json.dumps(historical_context, indent=2) if historical_context else ''}

Based on this information, please provide:
1. Assessment of attack likelihood (LOW/MEDIUM/HIGH/CRITICAL)
2. Recommended attack type classification
3. Suggested response actions (MONITOR/ALERT/RATE_LIMIT/BLOCK)
4. Confidence in your assessment
5. Whether to share this alert with neighbor nodes

Respond in JSON format:
{{
  "threat_level": "...",
  "attack_type": "...",
  "recommended_action": "...",
  "confidence": 0.XX,
  "share_alert": true/false,
  "reasoning": "..."
}}"""
        return query

    @staticmethod
    def format_coordination_query(
        alerts: List[Dict[str, Any]],
        network_state: Dict[str, Any]
    ) -> str:
        """Format query for coordination agent"""
        query = f"""Network-Wide Coordination Request:

RECEIVED ALERTS FROM NODES:
{json.dumps(alerts, indent=2)}

NETWORK STATE:
{json.dumps(network_state, indent=2)}

Please provide system-wide coordination recommendations:
1. Overall threat assessment
2. Coordinated mitigation strategy
3. Resource allocation priorities
4. Node trust score adjustments
5. Communication priorities

Respond in JSON format:
{{
  "overall_threat": "...",
  "mitigation_strategy": "...",
  "priority_nodes": [...],
  "trust_adjustments": {{}},
  "reasoning": "..."
}}"""
        return query

    @staticmethod
    def format_trust_query(
        node_id: str,
        model_update_stats: Dict[str, Any],
        historical_performance: Dict[str, float],
        current_trust_score: float
    ) -> str:
        """Format query for trust assessment agent"""
        query = f"""Trust Assessment Request for Node: {node_id}

MODEL UPDATE STATISTICS:
{json.dumps(model_update_stats, indent=2)}

HISTORICAL PERFORMANCE:
{json.dumps(historical_performance, indent=2)}

CURRENT TRUST SCORE: {current_trust_score:.3f}

Please assess:
1. Is this model update trustworthy?
2. Are there signs of Byzantine behavior or poisoning?
3. Should the trust score be adjusted? By how much?
4. Should this node be quarantined?
5. Anomaly indicators detected

Respond in JSON format:
{{
  "trustworthy": true/false,
  "byzantine_indicators": [...],
  "new_trust_score": 0.XXX,
  "quarantine": true/false,
  "anomaly_score": 0.XX,
  "reasoning": "..."
}}"""
        return query


class AgentDecisionEngine:
    """High-level agent decision engine using OpenRouter"""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        """
        Initialize decision engine
        
        Args:
            openrouter_client: OpenRouterClient instance
        """
        self.client = openrouter_client
        self.decision_history = []
        
    async def detect_and_classify(
        self,
        traffic_features: Dict[str, float],
        model_prediction: str,
        confidence: float,
        historical_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Get DDoS detection decision from agent
        
        Args:
            traffic_features: Current traffic features
            model_prediction: Model's prediction
            confidence: Prediction confidence
            historical_context: Historical context
            
        Returns:
            Detection decision dictionary
        """
        logger.info(f"Requesting detection decision for: {model_prediction}")
        
        query = DDoSAgentPrompts.format_detection_query(
            traffic_features, model_prediction, confidence, historical_context
        )
        
        response = await self.client.get_agent_decision(
            system_prompt=DDoSAgentPrompts.DETECTION_AGENT_SYSTEM,
            user_query=query,
            temperature=0.2
        )
        
        # Parse JSON response
        try:
            decision = json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON response, using raw: {response}")
            decision = {"raw_response": response}
        
        # Log decision
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "detection",
            "decision": decision
        })
        
        return decision
    
    async def coordinate_response(
        self,
        alerts: List[Dict[str, Any]],
        network_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get coordination decision for network-wide response
        
        Args:
            alerts: List of alerts from nodes
            network_state: Current network state
            
        Returns:
            Coordination decision
        """
        logger.info(f"Requesting coordination for {len(alerts)} alerts")
        
        query = DDoSAgentPrompts.format_coordination_query(alerts, network_state)
        
        response = await self.client.get_agent_decision(
            system_prompt=DDoSAgentPrompts.COORDINATION_AGENT_SYSTEM,
            user_query=query,
            temperature=0.3
        )
        
        try:
            decision = json.loads(response)
        except json.JSONDecodeError:
            decision = {"raw_response": response}
        
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "coordination",
            "decision": decision
        })
        
        return decision
    
    async def assess_trust(
        self,
        node_id: str,
        model_update_stats: Dict[str, Any],
        historical_performance: Dict[str, float],
        current_trust_score: float
    ) -> Dict[str, Any]:
        """
        Assess node trust and model update integrity
        
        Args:
            node_id: Node identifier
            model_update_stats: Statistics of model update
            historical_performance: Historical performance metrics
            current_trust_score: Current trust score
            
        Returns:
            Trust assessment decision
        """
        logger.info(f"Assessing trust for node: {node_id}")
        
        query = DDoSAgentPrompts.format_trust_query(
            node_id, model_update_stats, historical_performance, current_trust_score
        )
        
        response = await self.client.get_agent_decision(
            system_prompt=DDoSAgentPrompts.TRUST_ASSESSMENT_SYSTEM,
            user_query=query,
            temperature=0.1  # Very deterministic for security decisions
        )
        
        try:
            decision = json.loads(response)
        except json.JSONDecodeError:
            decision = {"raw_response": response}
        
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": "trust_assessment",
            "node_id": node_id,
            "decision": decision
        })
        
        return decision
    
    def get_decision_history(self, decision_type: Optional[str] = None) -> List[Dict]:
        """
        Get decision history
        
        Args:
            decision_type: Filter by type (detection/coordination/trust_assessment)
            
        Returns:
            List of decisions
        """
        if decision_type:
            return [d for d in self.decision_history if d['type'] == decision_type]
        return self.decision_history
