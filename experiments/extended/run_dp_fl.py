"""
Differential Privacy FL Experiment

Tests FL with varying privacy levels (epsilon values)
to analyze privacy-utility trade-off.
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.differential_privacy import DifferentialPrivacy, PrivacyAccountant
from projects.fl.aggregation_server import FederatedServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


def run_dp_fl(
    epsilon: float,
    num_nodes: int = 5,
    num_rounds: int = 15,
    data_tuple=None
):
    """
    Run FL with differential privacy.
    
    Args:
        epsilon: Privacy budget per round
        num_nodes: Number of FL nodes
        num_rounds: Number of FL rounds
        data_tuple: Pre-loaded data
        
    Returns:
        DP-FL results
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"DP-FL with ε={epsilon}")
    logger.info(f"{'='*70}")
    
    X_train_r, X_test_r, y_train, y_test, build_model = data_tuple
    
    # Initialize DP mechanism
    dp = DifferentialPrivacy(
        epsilon=epsilon,
        delta=1e-5,
        clip_norm=1.0
    )
    
    # Privacy accountant
    accountant = PrivacyAccountant(
        epsilon_budget=epsilon * num_rounds,
        delta_budget=1e-5 * num_rounds
    )
    
    # Fixed seed
    np.random.seed(42)
    
    # Split data
    indices = np.random.permutation(len(X_train_r))
    splits = np.array_split(indices, num_nodes)
    node_datasets = [(X_train_r[split], y_train[split]) for split in splits]
    
    # Initialize server with DP
    global_model = build_model()
    
    class DPFLServer(FederatedServer):
        def __init__(self, global_model, num_rounds, dp_mechanism, accountant):
            super().__init__(global_model, num_rounds)
            self.dp = dp_mechanism
            self.accountant = accountant
            self.round_accuracies = []
        
        def run_dp_round(self, local_updates, X_test, y_test):
            self.current_round += 1
            
            # Extract weights
            weights_list = [update['weights'] for update in local_updates.values()]
            data_sizes = [self.registered_nodes[nid]['data_size'] for nid in local_updates.keys()]
            
            # Apply DP to each update
            dp_weights_list = self.dp.privatize_batch(weights_list)
            
            # FedAvg
            aggregated = self.federated_averaging(dp_weights_list, data_sizes)
            self.global_model.set_weights(aggregated)
            
            # Track privacy spending
            self.accountant.spend(self.dp.epsilon, self.dp.delta)
           
            # Evaluate
            results = self.global_model.evaluate(X_test, y_test, verbose=0)
            self.round_accuracies.append(float(results[1]))
            
            if self.current_round % 5 == 0:
                summary = self.accountant.summary()
                logger.info(f"  Round {self.current_round}: Acc={results[1]:.4f}, "
                           f"ε spent={summary['epsilon_spent']:.2f}/{summary['epsilon_budget']}")
            
            return results
    
    fl_server = DPFLServer(global_model, num_rounds, dp, accountant)
    
    # Initialize nodes
    fl_nodes = {}
    for i in range(num_nodes):
        node_id = f"node_{i+1}"
        X_node, y_node = node_datasets[i]
        
        node = FLNode(
            node_id=node_id,
            local_data=(X_node, y_node),
            model_builder_fn=build_model,
            epochs_per_round=3,
            batch_size=64
        )
        
        fl_server.register_node(node_id, len(X_node))
        fl_nodes[node_id] = node
    
    logger.info(f"✓ {num_nodes} nodes initialized")
    
    # Run FL rounds
    for round_num in range(1, num_rounds + 1):
        global_weights = fl_server.get_global_model_weights()
        
        local_updates = {}
        for node_id, node in fl_nodes.items():
            update = node.participate_in_round(global_weights, verbose=0)
            local_updates[node_id] = update
        
        fl_server.run_dp_round(local_updates, X_test_r, y_test)
    
    # Final results
    final = global_model.evaluate(X_test_r, y_test, verbose=0)
    privacy_summary = accountant.summary()
    
    logger.info(f"\n✓ DP-FL Complete (ε={epsilon}):")
    logger.info(f"  Final Accuracy: {final[1]:.4f}")
    logger.info(f"  Privacy spent: ε={privacy_summary['epsilon_spent']:.2f}")
    
    return {
        'epsilon': epsilon,
        'final_accuracy': float(final[1]),
        'final_loss': float(final[0]),
        'round_accuracies': fl_server.round_accuracies,
        'privacy_summary': privacy_summary
    }


def run_dp_experiment(
    epsilon_values=[10.0, 1.0, 0.1],
    num_rounds=15
):
    """Run DP experiment with multiple epsilon values"""
    
    logger.info(f"\n{'='*70}")
    logger.info("DIFFERENTIAL PRIVACY FL EXPERIMENT")
    logger.info(f"{'='*70}")
    
    # Load data
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
    
    # Run for each epsilon
    all_results = []
    
    for epsilon in epsilon_values:
        result = run_dp_fl(
            epsilon=epsilon,
            num_nodes=5,
            num_rounds=num_rounds,
            data_tuple=data_tuple
        )
        all_results.append(result)
    
    # Print comparison
    print_dp_results(all_results)
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"results/dp_experiment_{timestamp}.json"
    
    import os
    os.makedirs('results', exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    logger.info(f"\n✓ Results saved to: {results_file}")
    
    return all_results


def print_dp_results(results):
    """Print DP comparison table"""
    
    logger.info(f"\n{'='*70}")
    logger.info("DIFFERENTIAL PRIVACY RESULTS")
    logger.info(f"{'='*70}")
    
    logger.info(f"\n{'Epsilon':<12} {'Accuracy':<12} {'Privacy Level':<20}")
    logger.info("-" * 70)
    
    privacy_levels = {
        0.1: "Strong",
        1.0: "Moderate",
        10.0: "Weak"
    }
    
    for result in results:
        eps = result['epsilon']
        acc = result['final_accuracy']
        level = privacy_levels.get(eps, "Custom")
        
        logger.info(f"{eps:<12} {acc:<12.4f} {level:<20}")
    
    logger.info(f"{'='*70}")
    
    # Analysis
    logger.info("\n📊 Privacy-Utility Trade-off:")
    for i, result in enumerate(results):
        logger.info(f"  ε={result['epsilon']}: {result['final_accuracy']:.4f} accuracy")


def main():
    """Run DP experiment"""
    
    EPSILON_VALUES = [10.0, 1.0, 0.1]  # Weak → Strong privacy
    NUM_ROUNDS = 15
    
    logger.info("Starting Differential Privacy experiment...")
    logger.info(f"Testing with ε: {EPSILON_VALUES}")
    
    results = run_dp_experiment(
        epsilon_values=EPSILON_VALUES,
        num_rounds=NUM_ROUNDS
    )
    
    return results


if __name__ == "__main__":
    main()
