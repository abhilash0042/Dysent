"""
Multi-LLM Coordinator for Comparative FL Experiments

Tests multiple LLM models (GPT-4, Claude, Llama, Mixtral) for FL coordination
and compares their effectiveness in threat assessment and strategy selection.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from projects.shared_libs.simple_openrouter import SimpleOpenRouterClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiLLMCoordinator:
    """
    Coordinate FL using multiple LLM models for comparison.
    
    Supported Models:
    - GPT-3.5-turbo (baseline)
    - GPT-4-turbo (best reasoning)
    - Claude 3.5 Sonnet (strong analysis)
    - Llama 3.1 70B (open-source)
    - Mixtral 8x7B (open-source alternative)
    """
    
    # Model configurations
    AVAILABLE_MODELS = {
        'gpt-3.5-turbo': {
            'name': 'GPT-3.5 Turbo',
            'provider': 'OpenAI',
            'cost_per_1k_tokens': 0.0015,
            'type': 'proprietary'
        },
        'gpt-4-turbo': {
            'name': 'GPT-4 Turbo',
            'provider': 'OpenAI',
            'cost_per_1k_tokens': 0.01,
            'type': 'proprietary'
        },
        'anthropic/claude-3.5-sonnet': {
            'name': 'Claude 3.5 Sonnet',
            'provider': 'Anthropic',
            'cost_per_1k_tokens': 0.003,
            'type': 'proprietary'
        },
        'perplexity/llama-3.1-sonar-large-128k-online': {
            'name': 'Perplexity Sonar Large',
            'provider': 'Perplexity',
            'cost_per_1k_tokens': 0.001,
            'type': 'proprietary'
        },
        'meta-llama/llama-3.1-70b-instruct': {
            'name': 'Llama 3.1 70B',
            'provider': 'Meta',
            'cost_per_1k_tokens': 0.0008,
            'type': 'open-source'
        },
        'mistralai/mixtral-8x7b-instruct': {
            'name': 'Mixtral 8x7B',
            'provider': 'Mistral AI',
            'cost_per_1k_tokens': 0.0006,
            'type': 'open-source'
        }
    }
    
    def __init__(self, models_to_test: Optional[List[str]] = None):
        """
        Initialize multi-LLM coordinator.
        
        Args:
            models_to_test: List of model IDs to test. If None, tests all.
        """
        if models_to_test is None:
            models_to_test = list(self.AVAILABLE_MODELS.keys())
        
        self.models_to_test = models_to_test
        self.llm_clients = {}
        self.results = {}
        
        # Initialize clients
        for model_id in models_to_test:
            if model_id in self.AVAILABLE_MODELS:
                logger.info(f"Initializing {self.AVAILABLE_MODELS[model_id]['name']}...")
                self.llm_clients[model_id] = SimpleOpenRouterClient(
                    model=model_id,
                    test_on_init=False  # Don't test yet, will test during experiment
                )
                self.results[model_id] = {
                    'model_info': self.AVAILABLE_MODELS[model_id],
                    'assessments': [],
                    'strategies': [],
                    'response_times': [],
                    'errors': 0,
                    'total_tokens': 0,
                    'total_cost': 0.0
                }
            else:
                logger.warning(f"Unknown model: {model_id}")
        
        logger.info(f"Multi-LLM Coordinator initialized with {len(self.llm_clients)} models")
    
    def assess_fl_round_multi_llm(
        self,
        round_data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Assess FL round using ALL LLMs and compare results.
        
        Args:
            round_data: FL round information
            
        Returns:
            Dictionary mapping model_id to assessment result
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"Multi-LLM Assessment - Round {round_data.get('round_number', 'N/A')}")
        logger.info(f"{'='*70}")
        
        assessments = {}
        
        # Prepare event data
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "round": round_data.get('round_number'),
            "nodes": round_data.get('participating_nodes'),
            "trust_avg": sum(round_data.get('trust_scores', {}).values()) / max(len(round_data.get('trust_scores', {})), 1),
            "anomalies": len(round_data.get('anomalies_detected', [])),
            "accuracy": round_data.get('metrics', {}).get('accuracy', 0)
        }
        
        # Get assessment from each LLM
        for model_id, client in self.llm_clients.items():
            model_name = self.AVAILABLE_MODELS[model_id]['name']
            
            logger.info(f"\n🤖 {model_name}:")
            
            try:
                start_time = time.time()
                
                # Get assessment
                assessment = client.analyze_security_event(event_data)
                
                response_time = time.time() - start_time
                
                # Log results
                logger.info(f"  Threat Level: {assessment.get('threat_level', 'unknown').upper()}")
                logger.info(f"  Action: {assessment.get('action', 'none')}")
                logger.info(f"  Confidence: {assessment.get('confidence', 0):.2f}")
                logger.info(f"  Response Time: {response_time:.2f}s")
                
                # Store results
                assessments[model_id] = assessment
                self.results[model_id]['assessments'].append(assessment)
                self.results[model_id]['response_times'].append(response_time)
                
                # Estimate token usage and cost (approximate)
                estimated_tokens = len(json.dumps(event_data)) // 4 + 100  # Rough estimate
                token_cost = (estimated_tokens / 1000) * self.AVAILABLE_MODELS[model_id]['cost_per_1k_tokens']
                
                self.results[model_id]['total_tokens'] += estimated_tokens
                self.results[model_id]['total_cost'] += token_cost
                
            except Exception as e:
                logger.error(f"  Error: {str(e)}")
                self.results[model_id]['errors'] += 1
                assessments[model_id] = {
                    'threat_level': 'error',
                    'action': 'none',
                    'confidence': 0.0,
                    'reasoning': f'Error: {str(e)}'
                }
        
        # Compare assessments
        self._compare_assessments(assessments)
        
        return assessments
    
    def select_aggregation_multi_llm(
        self,
        round_stats: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Get aggregation strategy recommendations from all LLMs.
        
        Args:
            round_stats: Round statistics
            
        Returns:
            Dictionary mapping model_id to recommended strategy
        """
        logger.info(f"\n🔍 Multi-LLM Strategy Selection:")
        
        strategies = {}
        
        for model_id, client in self.llm_clients.items():
            model_name = self.AVAILABLE_MODELS[model_id]['name']
            
            try:
                start_time = time.time()
                
                strategy = client.recommend_aggregation_strategy(round_stats)
                
                response_time = time.time() - start_time
                
                logger.info(f"  {model_name}: {strategy} ({response_time:.2f}s)")
                
                strategies[model_id] = strategy
                self.results[model_id]['strategies'].append(strategy)
                self.results[model_id]['response_times'].append(response_time)
                
            except Exception as e:
                logger.error(f"  {model_name}: Error - {str(e)}")
                self.results[model_id]['errors'] += 1
                strategies[model_id] = 'fedavg'  # Default fallback
        
        return strategies
    
    def _compare_assessments(self, assessments: Dict[str, Dict[str, Any]]):
        """Compare and log assessment differences"""
        
        # Extract threat levels
        threat_levels = {mid: a.get('threat_level') for mid, a in assessments.items()}
        
        # Check for consensus
        unique_levels = set(threat_levels.values())
        
        if len(unique_levels) == 1:
            logger.info(f"\n✓ Consensus: All LLMs agree on threat level '{list(unique_levels)[0]}'")
        else:
            logger.warning(f"\n⚠ Disagreement: Different threat levels detected")
            for model_id, level in threat_levels.items():
                logger.warning(f"  - {self.AVAILABLE_MODELS[model_id]['name']}: {level}")
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive comparison summary.
        
        Returns:
            Comparison statistics across all models
        """
        summary = {}
        
        for model_id, results in self.results.items():
            model_info = self.AVAILABLE_MODELS[model_id]
            
            # Calculate statistics
            avg_response_time = sum(results['response_times']) / max(len(results['response_times']), 1)
            
            # Threat level distribution
            threat_counts = {'low': 0, 'medium': 0, 'high': 0, 'error': 0}
            for assessment in results['assessments']:
                level = assessment.get('threat_level', 'error')
                if level in threat_counts:
                    threat_counts[level] += 1
            
            # Strategy distribution
            strategy_counts = {}
            for strategy in results['strategies']:
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
            summary[model_id] = {
                'model_name': model_info['name'],
                'provider': model_info['provider'],
                'type': model_info['type'],
                'total_assessments': len(results['assessments']),
                'total_strategies': len(results['strategies']),
                'avg_response_time': avg_response_time,
                'threat_distribution': threat_counts,
                'strategy_distribution': strategy_counts,
                'errors': results['errors'],
                'total_cost': results['total_cost'],
                'cost_per_assessment': results['total_cost'] / max(len(results['assessments']), 1)
            }
        
        return summary
    
    def print_comparison_report(self):
        """Print detailed comparison report"""
        
        logger.info("\n" + "="*70)
        logger.info("MULTI-LLM COMPARISON REPORT")
        logger.info("="*70)
        
        summary = self.get_comparison_summary()
        
        # Print table header
        logger.info(f"\n{'Model':<25} {'Assessments':<12} {'Avg Time':<12} {'Errors':<8} {'Cost':<10}")
        logger.info("-" * 70)
        
        # Print each model
        for model_id, stats in summary.items():
            logger.info(
                f"{stats['model_name']:<25} "
                f"{stats['total_assessments']:<12} "
                f"{stats['avg_response_time']:<12.2f} "
                f"{stats['errors']:<8} "
                f"${stats['total_cost']:<9.4f}"
            )
        
        logger.info("\n" + "="*70)
        
        # Detailed breakdown
        for model_id, stats in summary.items():
            logger.info(f"\n{stats['model_name']} ({stats['type']}):")
            logger.info(f"  Provider: {stats['provider']}")
            logger.info(f"  Threat Distribution: {stats['threat_distribution']}")
            logger.info(f"  Strategy Distribution: {stats['strategy_distribution']}")
            logger.info(f"  Cost per Assessment: ${stats['cost_per_assessment']:.4f}")
        
        logger.info("\n" + "="*70)


def test_multi_llm():
    """Test multi-LLM coordinator"""
    
    logger.info("Testing Multi-LLM Coordinator...")
    
    # Initialize with subset for testing
    coordinator = MultiLLMCoordinator(
        models_to_test=['gpt-3.5-turbo', 'gpt-4-turbo']  # Start with 2 for testing
    )
    
    # Test assessment
    test_round = {
        'round_number': 1,
        'participating_nodes': 5,
        'trust_scores': {'node_1': 1.0, 'node_2': 0.9, 'node_3': 0.95, 'node_4': 0.85, 'node_5': 1.0},
        'anomalies_detected': [],
        'metrics': {'accuracy': 0.99}
    }
    
    assessments = coordinator.assess_fl_round_multi_llm(test_round)
    
    # Test strategy selection
    round_stats = {
        'trust_scores': [1.0, 0.9, 0.95, 0.85, 1.0],
        'anomalies': 0,
        'nodes_count': 5
    }
    
    strategies = coordinator.select_aggregation_multi_llm(round_stats)
    
    # Print report
    coordinator.print_comparison_report()
    
    return coordinator


if __name__ == "__main__":
    test_multi_llm()
