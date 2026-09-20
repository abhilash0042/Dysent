"""
Secure FL Simulation with Zero-Trust Security

Demonstrates FL with Byzantine-resistant aggregation and malicious node detection.
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.trust_manager import TrustManager
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator, MaliciousNodeSimulator
from projects.fl.aggregation_server import FederatedServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


class SecureFLServer(FederatedServer):
    """
    FL Server with zero-trust security integrated.
    """
    
    def __init__(self, global_model, num_rounds=20, aggregation_method='fedavg'):
        super().__init__(global_model, num_rounds)
        
        self.trust_manager = TrustManager(min_trust_threshold=0.5)
        self.aggregation_method = aggregation_method  # 'fedavg', 'krum', 'trimmed_mean', 'median'
        
        logger.info(f"Secure FL Server initialized with {aggregation_method} aggregation")
    
    def register_node_secure(self, node_id, data_size):
        """Register node with authentication"""
        # Register in trust manager
        credentials = self.trust_manager.register_node(node_id, {'data_size': data_size})
        
        # Register in FL server
        self.register_node(node_id, data_size)
        
        return credentials.api_key
    
    def run_secure_round(self, local_updates):
        """
        Run FL round with security checks.
        
        Args:
            local_updates: {node_id: {'weights': [...], 'metrics': {...}, 'api_key': str}}
        """
        self.current_round += 1
        
        logger.info("\n" + "="*70)
        logger.info(f" SECURE FL ROUND {self.current_round}/{self.num_rounds}")
        logger.info("="*70)
        
        # Step 1: Authenticate all nodes
        authenticated_updates = {}
        for node_id, update in local_updates.items():
            api_key = update.get('api_key', '')
            
            if self.trust_manager.authenticate_node(node_id, api_key):
                can_participate, reason = self.trust_manager.can_participate(node_id, self.current_round)
                
                if can_participate:
                    authenticated_updates[node_id] = update
                else:
                    logger.warning(f"✗ Node {node_id} denied: {reason}")
            else:
                logger.warning(f"✗ Authentication failed for {node_id}")
        
        if len(authenticated_updates) < 2:
            logger.error("Not enough trusted nodes for this round!")
            return None
        
        # Step 2: Validate model updates
        validated_updates = {}
        for node_id, update in authenticated_updates.items():
            is_valid, analysis = self.trust_manager.validate_model_update(
                node_id,
                update['weights']
            )
            
            if is_valid:
                validated_updates[node_id] = update
            else:
                logger.warning(f"✗ Invalid update from {node_id}: {analysis['anomalies']}")
        
        if len(validated_updates) < 2:
            logger.error("Not enough valid updates for this round!")
            return None
        
        logger.info(f"✓ {len(validated_updates)} trusted updates validated")
        
        # Step 3: Byzantine-resistant aggregation
        weights_list = [update['weights'] for update in validated_updates.values()]
        data_sizes = [self.registered_nodes[nid]['data_size'] for nid in validated_updates.keys()]
        
        if self.aggregation_method == 'krum':
            aggregated_weights = ByzantineRobustAggregator.krum(weights_list, num_byzantine=1)
        elif self.aggregation_method == 'trimmed_mean':
            aggregated_weights = ByzantineRobustAggregator.trimmed_mean(weights_list, trim_ratio=0.2)
        elif self.aggregation_method == 'median':
            aggregated_weights = ByzantineRobustAggregator.median(weights_list)
        else:  # fedavg
            aggregated_weights = self.federated_averaging(weights_list, data_sizes)
        
        # Step 4: Update global model
        self.global_model.set_weights(aggregated_weights)
        
        logger.info("✓ Global model updated securely")
        
        # Return summary
        return {
            'round': self.current_round,
            'num_updates': len(validated_updates),
            'aggregation_method': self.aggregation_method
        }


def run_secure_fl_simulation(
    num_nodes=5,
    num_malicious=1,
    num_rounds=20,
    aggregation_method='trimmed_mean'
):
    """
    Run FL simulation with malicious nodes and security.
    
    Args:
        num_nodes: Total number of nodes
        num_malicious: Number of malicious nodes
        num_rounds: FL training rounds
        aggregation_method: 'fedavg', 'krum', 'trimmed_mean', or 'median'
    """
    logger.info("\n" + "🔒"*35)
    logger.info("SECURE FEDERATED LEARNING SIMULATION")
    logger.info(f"Aggregation: {aggregation_method.upper()}")
    logger.info(f"Malicious nodes: {num_malicious}/{num_nodes}")
    logger.info("🔒"*35 + "\n")
    
    # Load data
    logger.info("Loading data...")
    data = np.load('data/processed/cicddos2019_full_processed.npz')
    X, y = data['X'], data['y']
    
    # Apply feature selection
    with open('data/processed/cicddos2019_full_processed_feature_selection.pkl', 'rb') as f:
        results = pickle.load(f)
    
    selected_indices = results['ensemble']['indices']
    X = X[:, selected_indices]
    
    logger.info(f"Using {len(selected_indices)} selected features")
    
    # Split data
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    
    # Reshape
    timesteps = 10
    X_train_r = reshape_for_cnn_bilstm(X_train, timesteps)
    X_test_r = reshape_for_cnn_bilstm(X_test, timesteps)
    
    # Split across nodes
    indices = np.random.permutation(len(X_train_r))
    splits = np.array_split(indices, num_nodes)
    node_datasets = [(X_train_r[split], y_train[split]) for split in splits]
    
    # Create model builder
    def build_model():
        model = CNNBiLSTMModel(
            input_shape=X_train_r.shape[1:],
            num_classes=len(np.unique(y)),
            cnn_filters=(64, 128),
            lstm_units=(64, 32),
            dropout_rate=0.5
        )
        return model.model
    
    # Initialize secure server
    global_model = build_model()
    fl_server = SecureFLServer(
        global_model=global_model,
        num_rounds=num_rounds,
        aggregation_method=aggregation_method
    )
    
    # Initialize nodes (some malicious)
    fl_nodes = {}
    malicious_nodes = set()
    
    for i in range(num_nodes):
        node_id = f"node_{i+1}"
        is_malicious = i < num_malicious
        
        X_node, y_node = node_datasets[i]
        
        # Poison data for malicious nodes
        if is_malicious:
            y_node = MaliciousNodeSimulator.label_flip_attack(y_node, flip_ratio=0.5)
            malicious_nodes.add(node_id)
            logger.warning(f"⚠ {node_id}: MALICIOUS (label flipping)")
        
        node = FLNode(
            node_id=node_id,
            local_data=(X_node, y_node),
            model_builder_fn=build_model,
            epochs_per_round=5,
            batch_size=64
        )
        
        # Register with server
        api_key = fl_server.register_node_secure(node_id, len(X_node))
        
        fl_nodes[node_id] = {
            'node': node,
            'api_key': api_key,
            'is_malicious': is_malicious
        }
    
    logger.info(f"\n✓ {num_nodes} nodes initialized ({num_malicious} malicious)")
    
    # Run FL rounds
    for round_num in range(1, num_rounds + 1):
        print(f"\n{'='*70}")
        logger.info(f"ROUND {round_num}/{num_rounds}")
        
        # Get global weights
        global_weights = fl_server.get_global_model_weights()
        
        # Collect updates
        local_updates = {}
        
        for node_id, node_data in fl_nodes.items():
            node = node_data['node']
            api_key = node_data['api_key']
            is_malicious = node_data['is_malicious']
            
            # Train locally
            update = node.participate_in_round(global_weights, verbose=0)
            
            # Poison weights for malicious nodes
            if is_malicious and np.random.rand() > 0.3:  # 70% of time, attack
                attack_type = np.random.choice(['gaussian', 'scale', 'byzantine'])
                
                if attack_type == 'gaussian':
                    update['weights'] = MaliciousNodeSimulator.gaussian_noise_attack(
                        update['weights'], noise_scale=0.5
                    )
                elif attack_type == 'scale':
                    update['weights'] = MaliciousNodeSimulator.model_poisoning_attack(
                        update['weights'], scale_factor=5.0
                    )
                else:
                    update['weights'] = MaliciousNodeSimulator.byzantine_attack(
                        update['weights']
                    )
            
            update['api_key'] = api_key
            local_updates[node_id] = update
        
        # Secure aggregation
        round_summary = fl_server.run_secure_round(local_updates)
        
        # Periodic evaluation
        if round_num % 5 == 0:
            logger.info(f"\nEvaluating global model...")
            test_results = global_model.evaluate(X_test_r, y_test, verbose=0)
            logger.info(f"  Test Accuracy: {test_results[1]:.4f}")
    
    # Final evaluation
    logger.info("\n" + "="*70)
    logger.info("FINAL EVALUATION")
    logger.info("="*70)
    
    final_results = global_model.evaluate(X_test_r, y_test, verbose=0)
    logger.info(f"\nFinal Accuracy: {final_results[1]:.4f}")
    logger.info(f"Final Loss: {final_results[0]:.4f}")
    
    # Trust summary
    fl_server.trust_manager.summary()
    
    # Show detected malicious nodes
    logger.info("\n" + "="*70)
    logger.info("MALICIOUS NODE DETECTION")
    logger.info("="*70)
    logger.info(f"Actual malicious nodes: {malicious_nodes}")
    logger.info(f"Quarantined nodes: {fl_server.trust_manager.quarantined_nodes}")
    
    detected = malicious_nodes & fl_server.trust_manager.quarantined_nodes
    logger.info(f"✓ Detected: {len(detected)}/{num_malicious}")
    
    return fl_server, fl_nodes, global_model


def main():
    """Run secure FL simulation"""
    
    # Configuration
    NUM_NODES = 5
    NUM_MALICIOUS = 2  # 2 malicious nodes
    NUM_ROUNDS = 20
    AGGREGATION = 'trimmed_mean'  # Byzantine-resistant
    
    fl_server, fl_nodes, model = run_secure_fl_simulation(
        num_nodes=NUM_NODES,
        num_malicious=NUM_MALICIOUS,
        num_rounds=NUM_ROUNDS,
        aggregation_method=AGGREGATION
    )
    
    logger.info("\n✅ Secure FL simulation complete!")
    
    return fl_server, fl_nodes, model


if __name__ == "__main__":
    main()
