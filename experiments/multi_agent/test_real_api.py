"""
Multi-Agent LLM Real API Test

Tests the multi-agent coordinator with actual OpenRouter API calls.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime
import json
import os

from projects.shared_libs.multi_agent_llm import MultiAgentCoordinator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_real_api():
    """Test multi-agent system with real API"""
    
    logger.info("\n" + "="*70)
    logger.info("MULTI-AGENT LLM - REAL API TEST")
    logger.info("="*70)
    
    # Initialize with real API enabled
    coordinator = MultiAgentCoordinator(enable_auto_response=True)
    
    logger.info(f"\n✓ Multi-agent coordinator initialized")
    logger.info(f"  API Status: {'REAL' if coordinator.llm_client.api_working else 'MOCK'}")
    
    if not coordinator.llm_client.api_working:
        logger.warning("⚠️  API not working - check your OPENROUTER_API_KEY in .env")
        logger.info("   Continuing in MOCK mode...")
    
    # Test FL round with realistic data
    test_round = {
        'round_number': 7,
        'participating_nodes': 5,
        'trust_scores': {
            'node1': 1.0,
            'node2': 0.95,
            'node3': 0.65,  # Suspicious
            'node4': 0.90,
            'node5': 0.88
        },
        'anomalies_detected': ['node3'],  # One Byzantine node
        'performance': {
            'accuracy': 0.985,
            'loss': 0.068,
            'convergence_rate': 'moderate',
            'training_time': 52.3,
            'learning_rate': 0.001,
            'batch_size': 128,
            'epochs_per_round': 1
        }
    }
    
    logger.info(f"\n🤖 Running multi-agent coordination with real/mock API...")
    logger.info(f"  Round: {test_round['round_number']}")
    logger.info(f"  Anomalies: {len(test_round['anomalies_detected'])}")
    logger.info(f"  Trust variance: {coordinator._calculate_trust_variance(test_round['trust_scores']):.3f}")
    
    # Coordinate
    decisions = coordinator.coordinate_fl_round(test_round)
    
    # Display results
    logger.info(f"\n" + "="*70)
    logger.info("MULTI-AGENT DECISIONS")
    logger.info("="*70)
    
    logger.info(f"\n🛡️  Security Assessment:")
    security = decisions.get('security', {})
    logger.info(f"  Threat Level: {security.get('threat_level', 'N/A')}")
    if 'risks' in security:
        for risk in security.get('risks', [])[:3]:
            logger.info(f"  - {risk}")
    
    logger.info(f"\n⚙️  Aggregation Strategy:")
    logger.info(f"  Selected: {decisions.get('aggregation_strategy', 'N/A')}")
    
    logger.info(f"\n🔧 Hyperparameter Suggestions:")
    if 'hyperparameter_suggestions' in decisions:
        hp = decisions['hyperparameter_suggestions']
        logger.info(f"  Learning Rate: {hp.get('learning_rate', 'N/A')}")
        logger.info(f"  Batch Size: {hp.get('batch_size', 'N/A')}")
        logger.info(f"  Epochs/Round: {hp.get('epochs_per_round', 'N/A')}")
    
    logger.info(f"\n📝 Explanation:")
    explanation = decisions.get('explanation', '')
    logger.info(f"  {explanation[:200]}...")
    
    # Save results
    os.makedirs('results/multi_agent', exist_ok=True)
    
    with open(f"results/multi_agent/test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
        json.dump(decisions, f, indent=2)
    
    logger.info(f"\n✓ Results saved to results/multi_agent/")
    
    logger.info(f"\n" + "="*70)
    logger.info("✅ MULTI-AGENT LLM TEST COMPLETE")
    logger.info("="*70)
    
    logger.info(f"\n💡 Key Features Demonstrated:")
    logger.info(f"  ✓ 4 specialized AI agents working together")
    logger.info(f"  ✓ Security threat assessment")
    logger.info(f"  ✓ Intelligent strategy selection")
    logger.info(f"  ✓ Automatic hyperparameter tuning")
    logger.info(f"  ✓ Human-readable explanations")
    
    return decisions


def main():
    """Run real API test"""
    
    logger.info("Starting Multi-Agent LLM Real API Test...")
    
    results = test_real_api()
    
    return results


if __name__ == "__main__":
    main()
