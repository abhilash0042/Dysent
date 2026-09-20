"""
Scalability Experiment: Large-Scale FL Deployment

Tests FL system with increasing number of nodes (10, 20, 50)
to prove scalability and identify optimal deployment size.
"""

import sys
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pickle
import logging
from datetime import datetime
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.trust_manager import TrustManager
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator, MaliciousNodeSimulator
from projects.shared_libs.simple_openrouter import SimpleOpenRouterClient
from projects.shared_libs.agent_coordinator import FLAgentCoordinator
from projects.fl.aggregation_server import FederatedServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


def run_scalability_test(
    num_nodes: int,
    num_rounds: int = 15,
    malicious_ratio: float = 0.2,  # 20% malicious
    data_tuple=None,
    use_llm: bool = False
):
    """
    Run FL simulation with specified number of nodes.
    
    Args:
        num_nodes: Number of FL nodes to test
        num_rounds: Number of FL rounds
        malicious_ratio: Fraction of malicious nodes
        data_tuple: Pre-loaded data
        use_llm: Whether to use LLM coordination
        
    Returns:
        Scalability test results
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"SCALABILITY TEST: {num_nodes} NODES")
    logger.info(f"{'='*70}")
    
    start_time = time.time()
    
    # Unpack data
    X_train_r, X_test_r, y_train, y_test, build_model = data_tuple
    
    # Calculate malicious nodes
    num_malicious = max(1, int(num_nodes * malicious_ratio))
    
    logger.info(f"Configuration:")
    logger.info(f"  Total nodes: {num_nodes}")
    logger.info(f"  Malicious nodes: {num_malicious} ({malicious_ratio*100:.0f}%)")
    logger.info(f"  Rounds: {num_rounds}")
    logger.info(f"  LLM Coordination: {'Yes' if use_llm else 'No'}")
    
    # Fixed random seed for consistent comparison
    np.random.seed(42)
    
    # Split data across nodes
    indices = np.random.permutation(len(X_train_r))
    splits = np.array_split(indices, num_nodes)
    node_datasets = [(X_train_r[split], y_train[split]) for split in splits]
    
    # Initialize server
    global_model = build_model()
    
    class ScalableServer(FederatedServer):
        def __init__(self, global_model, num_rounds, use_llm=False):
            super().__init__(global_model, num_rounds)
            self.trust_manager = TrustManager(min_trust_threshold=0.5)
            self.use_llm = use_llm
            if use_llm:
                self.agent = FLAgentCoordinator(enable_auto_response=False)
            self.round_times = []
            self.round_accuracies = []
        
        def run_scalable_round(self, local_updates, X_test, y_test):
            round_start = time.time()
            self.current_round += 1
            
            # Authenticate
            authenticated_updates = {}
            trust_scores = {}
            
            for node_id, update in local_updates.items():
                api_key = update.get('api_key', '')
                if self.trust_manager.authenticate_node(node_id, api_key):
                    can_participate, _ = self.trust_manager.can_participate(node_id, self.current_round)
                    if can_participate:
                        authenticated_updates[node_id] = update
                        trust_scores[node_id] = self.trust_manager.get_trust_score(node_id)
            
            # Validate
            validated_updates = {}
            anomalies_detected = []
            
            for node_id, update in authenticated_updates.items():
                is_valid, analysis = self.trust_manager.validate_model_update(node_id, update['weights'])
                if is_valid:
                    validated_updates[node_id] = update
                else:
                    anomalies_detected.append({'node_id': node_id})
            
            # Aggregation strategy
            if self.use_llm and self.current_round % 5 == 0:  # LLM every 5 rounds to save cost
                round_data = {
                    'round_number': self.current_round,
                    'participating_nodes': len(validated_updates),
                    'trust_scores': trust_scores,
                    'anomalies_detected': anomalies_detected
                }
                assessment = self.agent.assess_fl_round(round_data)
                strategy = self.agent.select_aggregation_strategy({
                    'trust_scores': list(trust_scores.values()),
                    'anomalies': len(anomalies_detected),
                    'nodes_count': len(validated_updates)
                }, 'trimmed_mean')
            else:
                strategy = 'trimmed_mean'  # Default secure strategy
            
            # Aggregate
            weights_list = [update['weights'] for update in validated_updates.values()]
            data_sizes = [self.registered_nodes[nid]['data_size'] for nid in validated_updates.keys()]
            
            if strategy == 'krum':
                aggregated_weights = ByzantineRobustAggregator.krum(weights_list, num_byzantine=num_malicious)
            elif strategy == 'trimmed_mean':
                aggregated_weights = ByzantineRobustAggregator.trimmed_mean(weights_list)
            elif strategy == 'median':
                aggregated_weights = ByzantineRobustAggregator.median(weights_list)
            else:
                aggregated_weights = self.federated_averaging(weights_list, data_sizes)
            
            self.global_model.set_weights(aggregated_weights)
            
            # Evaluate
            round_results = self.global_model.evaluate(X_test, y_test, verbose=0)
            round_time = time.time() - round_start
            
            self.round_times.append(round_time)
            self.round_accuracies.append(float(round_results[1]))
            
            if self.current_round % 5 == 0:
                logger.info(f"  Round {self.current_round}/{self.num_rounds}: Acc={round_results[1]:.4f}, Time={round_time:.1f}s")
            
            return {'round': self.current_round, 'accuracy': round_results[1], 'time': round_time}
    
    fl_server = ScalableServer(global_model, num_rounds, use_llm=use_llm)
    
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
            epochs_per_round=2,  # Reduced for larger scale
            batch_size=64
        )
        
        credentials = fl_server.trust_manager.register_node(node_id, {'data_size': len(X_node)})
        fl_server.register_node(node_id, len(X_node))
        
        fl_nodes[node_id] = {
            'node': node,
            'api_key': credentials.api_key,
            'is_malicious': is_malicious
        }
    
    logger.info(f"\n✓ {num_nodes} nodes initialized")
    
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
                update['weights'] = MaliciousNodeSimulator.gaussian_noise_attack(update['weights'], noise_scale=0.2)
            
            update['api_key'] = api_key
            local_updates[node_id] = update
        
        fl_server.run_scalable_round(local_updates, X_test_r, y_test)
    
    # Final evaluation
    final_results = global_model.evaluate(X_test_r, y_test, verbose=0)
    total_time = time.time() - start_time
    
    logger.info(f"\n✓ Scalability Test Complete:")
    logger.info(f"  Final Accuracy: {final_results[1]:.4f}")
    logger.info(f"  Final Loss: {final_results[0]:.4f}")
    logger.info(f"  Total Time: {total_time:.1f}s ({total_time/60:.1f} min)")
    logger.info(f"  Avg Time/Round: {np.mean(fl_server.round_times):.1f}s")
    
    return {
        'num_nodes': num_nodes,
        'num_malicious': num_malicious,
        'num_rounds': num_rounds,
        'final_accuracy': float(final_results[1]),
        'final_loss': float(final_results[0]),
        'total_time': total_time,
        'avg_round_time': float(np.mean(fl_server.round_times)),
        'round_accuracies': fl_server.round_accuracies,
        'convergence_round': int(np.argmax(fl_server.round_accuracies)) + 1
    }


def run_scalability_experiment(
    node_counts=[5, 10, 20],  # Start with smaller for testing
    num_rounds=15
):
    """
    Run complete scalability comparison across different node counts.
    
    Args:
        node_counts: List of node counts to test
        num_rounds: Number of FL rounds per test
        
    Returns:
        Complete scalability results
    """
    logger.info("\n" + "="*70)
    logger.info("SCALABILITY EXPERIMENT: FL WITH VARIABLE NODE COUNTS")
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
    
    # Run tests for each node count
    all_results = []
    
    for num_nodes in node_counts:
        result = run_scalability_test(
            num_nodes=num_nodes,
            num_rounds=num_rounds,
            data_tuple=data_tuple,
            use_llm=False  # Disable LLM for speed
        )
        all_results.append(result)
    
    # Print comparison
    print_scalability_results(all_results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"results/scalability_experiment_{timestamp}.json"
    
    import os
    os.makedirs('results', exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"\n✓ Results saved to: {results_file}")
    
    return all_results


def print_scalability_results(results):
    """Print scalability comparison table"""
    
    logger.info("\n" + "="*70)
    logger.info("SCALABILITY RESULTS COMPARISON")
    logger.info("="*70)
    
    logger.info(f"\n{'Nodes':<8} {'Accuracy':<12} {'Time(min)':<12} {'Time/Round':<15} {'Convergence':<12}")
    logger.info("-" * 70)
    
    for result in results:
        logger.info(
            f"{result['num_nodes']:<8} "
            f"{result['final_accuracy']:<12.4f} "
            f"{result['total_time']/60:<12.1f} "
            f"{result['avg_round_time']:<15.1f} "
            f"Round {result['convergence_round']:<12}"
        )
    
    logger.info("="*70)
    
    # Analysis
    logger.info("\n📊 Scalability Analysis:")
    
    base = results[0]
    for result in results[1:]:
        accuracy_change = result['final_accuracy'] - base['final_accuracy']
        time_ratio = result['total_time'] / base['total_time']
        
        logger.info(f"\n{base['num_nodes']} → {result['num_nodes']} nodes:")
        logger.info(f"  Accuracy change: {accuracy_change:+.4f}")
        logger.info(f"  Time increase: {time_ratio:.2f}x")


def main():
    """Run scalability experiment"""
    
    # Configuration
    NODE_COUNTS = [5, 10, 20]  # Can add 50 if system handles it
    NUM_ROUNDS = 15
    
    logger.info("Starting scalability experiment...")
    logger.info(f"Testing with: {NODE_COUNTS} nodes")
    
    results = run_scalability_experiment(
        node_counts=NODE_COUNTS,
        num_rounds=NUM_ROUNDS
    )
    
    return results


if __name__ == "__main__":
    main()
