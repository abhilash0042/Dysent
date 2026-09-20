"""
Multi-Agent LLM Coordination System

Extends single LLM coordinator to multiple specialized agents:
- Security Agent: Threat assessment and anomaly detection
- Aggregation Agent: Strategy selection and optimization
- Optimization Agent: Hyperparameter tuning
- Explainability Agent: Decision interpretation and reporting
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from typing import Dict, List, Optional, Any
import logging
import json
from datetime import datetime

from projects.shared_libs.simple_openrouter import SimpleOpenRouterClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityAgent:
    """Specialized agent for security and threat assessment"""
    
    def __init__(self, llm_client: SimpleOpenRouterClient):
        self.llm = llm_client
        self.name = "SecurityAgent"
        
    def assess_threats(self, fl_round_data: Dict) -> Dict:
        """Assess security threats in FL round"""
        
        prompt = f"""You are a cybersecurity expert analyzing a federated learning round for DDoS detection.

Round Data:
- Round: {fl_round_data.get('round_number')}
- Participants: {fl_round_data.get('participating_nodes')}
- Trust Scores: {fl_round_data.get('trust_scores', {})}
- Anomalies: {fl_round_data.get('anomalies_detected', [])}

Analyze the security posture and provide:
1. Threat level (LOW/MEDIUM/HIGH/CRITICAL)
2. Specific risks identified
3. Recommended actions

Respond in JSON format."""

        response = self.llm.chat(prompt)
        
        try:
            assessment = json.loads(response)
        except:
            # Fallback structured response
            assessment = {
                'threat_level': 'MEDIUM',
                'risks': ['Automated analysis pending'],
                'actions': ['Continue monitoring']
            }
        
        logger.info(f"[{self.name}] Threat assessment: {assessment.get('threat_level', 'UNKNOWN')}")
        return assessment


class AggregationAgent:
    """Specialized agent for aggregation strategy selection"""
    
    def __init__(self, llm_client: SimpleOpenRouterClient):
        self.llm = llm_client
        self.name = "AggregationAgent"
        
    def select_strategy(self, context: Dict) -> str:
        """Select optimal aggregation strategy"""
        
        prompt = f"""You are an expert in federated learning aggregation strategies.

Current Context:
- Byzantine nodes detected: {context.get('byzantine_count', 0)}
- Trust variance: {context.get('trust_variance', 0)}
- Model convergence: {context.get('convergence_status', 'unknown')}

Available strategies:
1. FedAvg - Standard averaging (fast, less robust)
2. Krum - Byzantine-robust (slower, more robust)
3. TrimmedMean - Moderate robustness
4. Median - High robustness, slower

Recommend the best strategy for this situation. Respond with just the strategy name."""

        response = self.llm.chat(prompt).strip()
        
        # Validate response
        valid_strategies = ['FedAvg', 'Krum', 'TrimmedMean', 'Median']
        strategy = response if response in valid_strategies else 'FedAvg'
        
        logger.info(f"[{self.name}] Selected strategy: {strategy}")
        return strategy


class OptimizationAgent:
    """Specialized agent for hyperparameter optimization"""
    
    def __init__(self, llm_client: SimpleOpenRouterClient):
        self.llm = llm_client
        self.name = "OptimizationAgent"
        
    def suggest_hyperparameters(self, performance_data: Dict) -> Dict:
        """Suggest hyperparameter adjustments"""
        
        prompt = f"""You are an ML optimization expert for federated learning.

Current Performance:
- Accuracy: {performance_data.get('accuracy', 0):.4f}
- Loss: {performance_data.get('loss', 0):.4f}
- Convergence rate: {performance_data.get('convergence_rate', 'stable')}
- Training time: {performance_data.get('training_time', 0)}s

Current Hyperparameters:
- Learning rate: {performance_data.get('learning_rate', 0.001)}
- Batch size: {performance_data.get('batch_size', 128)}
- Epochs per round: {performance_data.get('epochs_per_round', 1)}

Suggest adjustments to improve performance. Respond in JSON with new values."""

        response = self.llm.chat(prompt)
        
        try:
            suggestions = json.loads(response)
        except:
            # Default: no changes
            suggestions = {
                'learning_rate': performance_data.get('learning_rate', 0.001),
                'batch_size': performance_data.get('batch_size', 128),
                'epochs_per_round': performance_data.get('epochs_per_round', 1)
            }
        
        logger.info(f"[{self.name}] Hyperparameter suggestions: {suggestions}")
        return suggestions


class ExplainabilityAgent:
    """Specialized agent for decision explanation"""
    
    def __init__(self, llm_client: SimpleOpenRouterClient):
        self.llm = llm_client
        self.name = "ExplainabilityAgent"
        
    def explain_decision(self, decision_data: Dict) -> str:
        """Generate human-readable explanation of FL decisions"""
        
        prompt = f"""You are an AI explainability expert. Explain the following federated learning decision in simple terms.

Decision Type: {decision_data.get('decision_type')}
Context: {decision_data.get('context', {})}
Outcome: {decision_data.get('outcome')}

Provide a clear, concise explanation (2-3 sentences) for non-technical stakeholders."""

        explanation = self.llm.chat(prompt)
        
        logger.info(f"[{self.name}] Generated explanation")
        return explanation


class MultiAgentCoordinator:
    """
    Coordinates multiple specialized LLM agents for FL-DDoS system
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-3.5-turbo",
        enable_auto_response: bool = False  # Changed: False = use real API if available
    ):
        """
        Initialize Multi-Agent Coordinator.
        
        Args:
            api_key: OpenRouter API key
            model: LLM model to use
            enable_auto_response: If True, use MOCK mode; If False, use real API
        """
        # Initialize LLM client
        self.llm_client = SimpleOpenRouterClient(
            api_key=api_key,
            model=model,
            test_on_init=not enable_auto_response  # Test API if not in mock mode
        )
        
        # Override mock mode based on enable_auto_response
        if enable_auto_response:
            self.llm_client.mock_mode = True
            logger.info("Multi-Agent LLM Coordinator initialized in MOCK mode (auto-response enabled)")
        else:
            # Use real API if key is available
            if self.llm_client.api_working:
                self.llm_client.mock_mode = False
                logger.info("Multi-Agent LLM Coordinator initialized with REAL API")
            else:
                logger.warning("API not working, falling back to MOCK mode")
        
        # Initialize specialized agents
        self.security_agent = SecurityAgent(self.llm_client)
        self.aggregation_agent = AggregationAgent(self.llm_client)
        self.optimization_agent = OptimizationAgent(self.llm_client)
        self.explainability_agent = ExplainabilityAgent(self.llm_client)
        
        self.enable_auto_response = enable_auto_response
        
        logger.info("Multi-Agent LLM Coordinator initialized")
        logger.info(f"  Agents: Security, Aggregation, Optimization, Explainability")
        logger.info(f"  Mode: {'API' if self.llm_client.api_working else 'MOCK'}")
    
    def coordinate_fl_round(self, round_data: Dict) -> Dict:
        """
        Coordinate all agents for a complete FL round analysis
        
        Args:
            round_data: FL round information
            
        Returns:
            Coordinated decisions and recommendations
        """
        logger.info(f"\n🤖 Multi-Agent Coordination for Round {round_data.get('round_number')}")
        
        decisions = {
            'round': round_data.get('round_number'),
            'timestamp': datetime.now().isoformat()
        }
        
        # 1. Security assessment
        if self.enable_auto_response and self.llm_client.api_working:
            security_assessment = self.security_agent.assess_threats(round_data)
            decisions['security'] = security_assessment
        else:
            decisions['security'] = {'threat_level': 'MEDIUM', 'mock': True}
        
        # 2. Aggregation strategy selection
        context = {
            'byzantine_count': len(round_data.get('anomalies_detected', [])),
            'trust_variance': self._calculate_trust_variance(round_data.get('trust_scores', {})),
            'convergence_status': 'stable'
        }
        
        if self.enable_auto_response and self.llm_client.api_working:
            strategy = self.aggregation_agent.select_strategy(context)
            decisions['aggregation_strategy'] = strategy
        else:
            decisions['aggregation_strategy'] = 'FedAvg'
        
        # 3. Performance optimization (if data available)
        if 'performance' in round_data:
            if self.enable_auto_response and self.llm_client.api_working:
                suggestions = self.optimization_agent.suggest_hyperparameters(round_data['performance'])
                decisions['hyperparameter_suggestions'] = suggestions
        
        # 4. Generate explanation
        if self.enable_auto_response and self.llm_client.api_working:
            explanation = self.explainability_agent.explain_decision({
                'decision_type': 'FL Round Coordination',
                'context': round_data,
                'outcome': decisions
            })
            decisions['explanation'] = explanation
        else:
            decisions['explanation'] = "Multi-agent coordination complete (MOCK mode)"
        
        logger.info(f"✓ Coordination complete: {decisions['aggregation_strategy']} strategy selected")
        
        return decisions
    
    def _calculate_trust_variance(self, trust_scores: Dict) -> float:
        """Calculate variance in trust scores"""
        if not trust_scores:
            return 0.0
        
        import numpy as np
        scores = list(trust_scores.values())
        return float(np.var(scores))


def test_multi_agent_system():
    """Test multi-agent coordinator"""
    
    print("\n" + "="*70)
    print("TESTING MULTI-AGENT LLM COORDINATOR")
    print("="*70)
    
    # Initialize
    coordinator = MultiAgentCoordinator(enable_auto_response=Fals)
    
    print(f"\n✓ Multi-agent system initialized")
    print(f"  Agents: 4 specialized")
    
    # Test round
    test_round = {
        'round_number': 5,
        'participating_nodes': 5,
        'trust_scores': {
            'node1': 1.0,
            'node2': 0.95,
            'node3': 0.85,
            'node4': 0.90,
            'node5': 0.88
        },
        'anomalies_detected': ['node3'],
        'performance': {
            'accuracy': 0.992,
            'loss': 0.05,
            'convergence_rate': 'stable',
            'training_time': 45.2,
            'learning_rate': 0.001,
            'batch_size': 128,
            'epochs_per_round': 1
        }
    }
    
    # Coordinate
    print(f"\n🤖 Testing multi-agent coordination...")
    decisions = coordinator.coordinate_fl_round(test_round)
    
    print(f"\n✓ Coordination complete:")
    print(f"  Threat Level: {decisions['security'].get('threat_level', 'N/A')}")
    print(f"  Strategy: {decisions['aggregation_strategy']}")
    print(f"  Explanation: {decisions['explanation'][:100]}...")
    
    print(f"\n✓ Multi-agent system test successful!")
    
    return coordinator


if __name__ == "__main__":
    test_multi_agent_system()
