"""
FL Simulation with Multi-LLM Comparison

Runs the FL simulation multiple times, once with each LLM model,
and compares their performance in coordinating the FL system.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


import sys
import numpy as np
import pickle
from pathlib import Path
import logging
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.trust_manager import TrustManager
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator, MaliciousNodeSimulator
from projects.shared_libs.multi_llm_coordinator import MultiLLMCoordinator
from projects.fl.aggregation_server import FederatedServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


def run_fl_with_llm(
    model_id: str,
    llm_coordinator: MultiLLMCoordinator,
    num_nodes=5,
    num_malicious=1,
    num_rounds=10,  # Shorter for comparison
    data_tuple=None
):
    """
    Run FL simulation with a specific LLM model.
    
    Args:
        model_id: LLM model identifier
        llm_coordinator: Multi-LLM coordinator instance
        num_nodes: Number of FL nodes
        num_malicious: Number of malicious nodes
        num_rounds: Number of FL rounds
        data_tuple: Pre-loaded data (X_train, X_test, y_train, y_test, build_model)
        
    Returns:
        FL results dictionary
    """
    model_name = MultiLLMCoordinator.AVAILABLE_MODELS[model_id]['name']
    
    logger.info(f"\n{'🤖'*35}")
    logger.info(f"FL SIMULATION WITH {model_name}")
    logger.info(f"{'🤖'*35}\n")
    
    # Unpack data
    X_train_r, X_test_r, y_train, y_test, build_model = data_tuple
    
    # CRITICAL FIX: Set random seed for consistent splits across all LLMs
    # This ensures fair comparison - all models get the SAME data distribution
    np.random.seed(42)
    
    # Split across nodes
    indices = np.random.permutation(len(X_train_r))
    splits = np.array_split(indices, num_nodes)
    node_datasets = [(X_train_r[split], y_train[split]) for split in splits]
    
    # Initialize server with trust manager
    global_model = build_model()
    
    class LLMCoordinatedServer(FederatedServer):
        def __init__(self, global_model, num_rounds, model_id, llm_coord):
            super().__init__(global_model, num_rounds)
            self.trust_manager = TrustManager(min_trust_threshold=0.5)
            self.model_id = model_id
            self.llm_coordinator = llm_coord
            self.round_results = []
        
        def run_llm_round(self, local_updates):
            self.current_round += 1
            
            # Authenticate and validate
            authenticated_updates = {}
            trust_scores = {}
            
            for node_id, update in local_updates.items():
                api_key = update.get('api_key', '')
                if self.trust_manager.authenticate_node(node_id, api_key):
                    can_participate, _ = self.trust_manager.can_participate(node_id, self.current_round)
                    if can_participate:
                        authenticated_updates[node_id] = update
                        trust_scores[node_id] = self.trust_manager.get_trust_score(node_id)
            
            # Validate updates
            validated_updates = {}
            anomalies_detected = []
            
            for node_id, update in authenticated_updates.items():
                is_valid, analysis = self.trust_manager.validate_model_update(node_id, update['weights'])
                if is_valid:
                    validated_updates[node_id] = update
                else:
                    anomalies_detected.append({'node_id': node_id, 'anomalies': analysis['anomalies']})
            
            # LLM Assessment for this specific model
            round_data = {
                'round_number': self.current_round,
                'participating_nodes': len(validated_updates),
                'trust_scores': trust_scores,
                'anomalies_detected': anomalies_detected,
                'metrics': {'authenticated': len(authenticated_updates), 'validated': len(validated_updates)}
            }
            
            # Get assessment from this specific LLM only
            assessment = self.llm_coordinator.llm_clients[self.model_id].analyze_security_event({
                "round": round_data['round_number'],
                "nodes": round_data['participating_nodes'],
                "trust_avg": sum(trust_scores.values()) / max(len(trust_scores), 1),
                "anomalies": len(anomalies_detected)
            })
            
            # Get strategy from this specific LLM only
            strategy = self.llm_coordinator.llm_clients[self.model_id].recommend_aggregation_strategy({
                'trust_scores': list(trust_scores.values()),
                'anomalies': len(anomalies_detected),
                'nodes_count': len(validated_updates)
            })
            
            # Aggregate based on LLM recommendation
            weights_list = [update['weights'] for update in validated_updates.values()]
            data_sizes = [self.registered_nodes[nid]['data_size'] for nid in validated_updates.keys()]
            
            if strategy == 'krum':
                aggregated_weights = ByzantineRobustAggregator.krum(weights_list, num_byzantine=1)
            elif strategy == 'trimmed_mean':
                aggregated_weights = ByzantineRobustAggregator.trimmed_mean(weights_list)
            elif strategy == 'median':
                aggregated_weights = ByzantineRobustAggregator.median(weights_list)
            else:
                aggregated_weights = self.federated_averaging(weights_list, data_sizes)
            
            self.global_model.set_weights(aggregated_weights)
            
            # Store round result
            self.round_results.append({
                'round': self.current_round,
                'assessment': assessment,
                'strategy': strategy,
                'threat_level': assessment.get('threat_level')
            })
            
            return {'round': self.current_round, 'strategy': strategy}
    
    fl_server = LLMCoordinatedServer(global_model, num_rounds, model_id, llm_coordinator)
    
    # Initialize nodes
    fl_nodes = {}
    for i in range(num_nodes):
        node_id = f"node_{i+1}"
        is_malicious = i < num_malicious
        
        X_node, y_node = node_datasets[i]
        
        if is_malicious:
            y_node = MaliciousNodeSimulator.label_flip_attack(y_node, flip_ratio=0.3)
        
        node = FLNode(
            node_id=node_id,
            local_data=(X_node, y_node),
            model_builder_fn=build_model,
            epochs_per_round=3,  # Faster
            batch_size=64
        )
        
        credentials = fl_server.trust_manager.register_node(node_id, {'data_size': len(X_node)})
        fl_server.register_node(node_id, len(X_node))
        
        fl_nodes[node_id] = {
            'node': node,
            'api_key': credentials.api_key,
            'is_malicious': is_malicious
        }
    
    # Run FL rounds
    for round_num in range(1, num_rounds + 1):
        global_weights = fl_server.get_global_model_weights()
        
        local_updates = {}
        for node_id, node_data in fl_nodes.items():
            node = node_data['node']
            api_key = node_data['api_key']
            is_malicious = node_data['is_malicious']
            
            update = node.participate_in_round(global_weights, verbose=0)
            
            if is_malicious and np.random.rand() > 0.5:
                update['weights'] = MaliciousNodeSimulator.gaussian_noise_attack(update['weights'], noise_scale=0.3)
            
            update['api_key'] = api_key
            local_updates[node_id] = update
        
        fl_server.run_llm_round(local_updates)
    
    # Final evaluation
    final_results = global_model.evaluate(X_test_r, y_test, verbose=0)
    
    logger.info(f"\n✓ {model_name} Complete:")
    logger.info(f"  Final Accuracy: {final_results[1]:.4f}")
    logger.info(f"  Final Loss: {final_results[0]:.4f}")
    
    return {
        'model_id': model_id,
        'model_name': model_name,
        'final_accuracy': float(final_results[1]),
        'final_loss': float(final_results[0]),
        'round_results': fl_server.round_results
    }


def run_multi_llm_experiment(
    models_to_test=None,
    num_rounds=10
):
    """
    Run complete multi-LLM comparison experiment.
    
    Args:
        models_to_test: List of model IDs to test
        num_rounds: Number of FL rounds per model
        
    Returns:
        Complete experiment results
    """
    logger.info("\n" + "="*70)
    logger.info("MULTI-LLM FL COMPARISON EXPERIMENT")
    logger.info("="*70)
    
    # Load data once
    logger.info("\nLoading data...")
    data = np.load('data/processed/cicddos2019_full_processed.npz')
    X, y = data['X'], data['y']
    
    with open('data/processed/cicddos2019_full_processed_feature_selection.pkl', 'rb') as f:
        results = pickle.load(f)
    
    X = X[:, results['ensemble']['indices']]
    
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    
    timesteps = 10
    X_train_r = reshape_for_cnn_bilstm(X_train, timesteps)
    X_test_r = reshape_for_cnn_bilstm(X_test, timesteps)
    
    def build_model():
        model = CNNBiLSTMModel(
            input_shape=X_train_r.shape[1:],
            num_classes=len(np.unique(y)),
            cnn_filters=(64, 128),
            lstm_units=(64, 32),
            dropout_rate=0.5
        )
        return model.model
    
    data_tuple = (X_train_r, X_test_r, y_train, y_test, build_model)
    
    # Initialize multi-LLM coordinator
    if models_to_test is None:
        models_to_test = ['gpt-3.5-turbo', 'gpt-4-turbo']  # Start with 2
    
    llm_coordinator = MultiLLMCoordinator(models_to_test=models_to_test)
    
    # Run FL with each LLM
    all_results = []
    
    for model_id in models_to_test:
        result = run_fl_with_llm(
            model_id,
            llm_coordinator,
            num_rounds=num_rounds,
            data_tuple=data_tuple
        )
        all_results.append(result)
    
    # Print comparison
    print_comparison_table(all_results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"results/multi_llm_comparison_{timestamp}.json"
    
    # Ensure directory exists
    import os
    os.makedirs('results', exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"\n✓ Results saved to: {results_file}")
    
    return all_results


def print_comparison_table(results):
    """Print comparison table of all LLM results"""
    
    logger.info("\n" + "="*70)
    logger.info("MULTI-LLM PERFORMANCE COMPARISON")
    logger.info("="*70)
    
    logger.info(f"\n{'Model':<30} {'Accuracy':<12} {'Loss':<12}")
    logger.info("-" * 70)
    
    for result in results:
        logger.info(
            f"{result['model_name']:<30} "
            f"{result['final_accuracy']:<12.4f} "
            f"{result['final_loss']:<12.4f}"
        )
    
    # Find best
    best = max(results, key=lambda x: x['final_accuracy'])
    
    logger.info(f"\n🏆 Best Model: {best['model_name']} ({best['final_accuracy']:.4f})")
    logger.info("="*70)


def main():
    """Run multi-LLM comparison experiment"""
    
    # Configuration
    MODELS_TO_TEST = [
        'gpt-3.5-turbo',  # Baseline
        'gpt-4-turbo',     # Advanced OpenAI
        'anthropic/claude-3.5-sonnet',  # Anthropic
        'perplexity/llama-3.1-sonar-large-128k-online'  # Perplexity
    ]
    
    NUM_ROUNDS = 10  # Shorter for faster comparison
    
    results = run_multi_llm_experiment(
        models_to_test=MODELS_TO_TEST,
        num_rounds=NUM_ROUNDS
    )
    
    return results


if __name__ == "__main__":
    main()
