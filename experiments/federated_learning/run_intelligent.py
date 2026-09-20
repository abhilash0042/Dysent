"""
FL Simulation with LLM-Based Intelligent Coordination

Demonstrates federated learning with AI-powered decision making,
adaptive security, and intelligent threat response.
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
from projects.shared_libs.agent_coordinator import FLAgentCoordinator
from projects.fl.aggregation_server import FederatedServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


class IntelligentFLServer(FederatedServer):
    """
    FL Server with LLM-based intelligent coordination.
    """
    
    def __init__(self, global_model, num_rounds=20):
        super().__init__(global_model, num_rounds)
        
        self.trust_manager = TrustManager(min_trust_threshold=0.5)
        self.agent = FLAgentCoordinator(enable_auto_response=False)
        self.current_strategy = 'fedavg'
        
        logger.info("Intelligent FL Server initialized with LLM coordination")
    
    def register_node_with_intelligence(self, node_id, data_size):
        """Register node with both trust manager and FL server"""
        # Register in trust manager
        credentials = self.trust_manager.register_node(node_id, {'data_size': data_size})
        
        # Register in parent FL server
        self.register_node(node_id, data_size)
        
        return credentials
    
    def run_intelligent_round(self, local_updates):
        """
        Run FL round with LLM intelligence.
        """
        self.current_round += 1
        
        logger.info("\n" + "🤖"*35)
        logger.info(f"INTELLIGENT FL ROUND {self.current_round}/{self.num_rounds}")
        logger.info("🤖"*35)
        
        # Step 1: Authenticate nodes
        authenticated_updates = {}
        trust_scores = {}
        
        for node_id, update in local_updates.items():
            api_key = update.get('api_key', '')
            
            if self.trust_manager.authenticate_node(node_id, api_key):
                can_participate, reason = self.trust_manager.can_participate(node_id, self.current_round)
                
                if can_participate:
                    authenticated_updates[node_id] = update
                    trust_scores[node_id] = self.trust_manager.get_trust_score(node_id)
        
        # Step 2: Validate updates
        validated_updates = {}
        anomalies_detected = []
        
        for node_id, update in authenticated_updates.items():
            is_valid, analysis = self.trust_manager.validate_model_update(
                node_id,
                update['weights']
            )
            
            if is_valid:
                validated_updates[node_id] = update
            else:
                anomalies_detected.append({
                    'node_id': node_id,
                    'anomalies': analysis['anomalies'],
                    'score': analysis['anomaly_score']
                })
        
        # Step 3: LLM Assessment
        round_data = {
            'round_number': self.current_round,
            'participating_nodes': len(validated_updates),
            'trust_scores': trust_scores,
            'anomalies_detected': anomalies_detected,
            'metrics': {
                'authenticated': len(authenticated_updates),
                'validated': len(validated_updates),
                'rejected': len(local_updates) - len(validated_updates)
            }
        }
        
        assessment = self.agent.assess_fl_round(round_data)
        
        # Step 4: Adaptive aggregation (LLM-selected)
        round_stats = {
            'trust_scores': list(trust_scores.values()),
            'anomalies': len(anomalies_detected),
            'nodes_count': len(validated_updates)
        }
        
        recommended_strategy = self.agent.select_aggregation_strategy(
            round_stats,
            self.current_strategy
        )
        
        # Use recommended strategy
        if recommended_strategy != self.current_strategy:
            logger.info(f"🔄 Switching aggregation: {self.current_strategy} → {recommended_strategy}")
            self.current_strategy = recommended_strategy
        
        # Aggregate
        weights_list = [update['weights'] for update in validated_updates.values()]
        data_sizes = [self.registered_nodes[nid]['data_size'] for nid in validated_updates.keys()]
        
        if self.current_strategy == 'krum':
            aggregated_weights = ByzantineRobustAggregator.krum(weights_list, num_byzantine=1)
        elif self.current_strategy == 'trimmed_mean':
            aggregated_weights = ByzantineRobustAggregator.trimmed_mean(weights_list)
        elif self.current_strategy == 'median':
            aggregated_weights = ByzantineRobustAggregator.median(weights_list)
        else:  # fedavg
            aggregated_weights = self.federated_averaging(weights_list, data_sizes)
        
        # Update global model
        self.global_model.set_weights(aggregated_weights)
        
        # Handle high threats
        if assessment.get('threat_level') == 'high' and anomalies_detected:
            incident = {
                'round': self.current_round,
                'anomalies': anomalies_detected,
                'trust_scores': trust_scores
            }
            self.agent.handle_security_incident(incident)
        
        logger.info("✓ Intelligent round complete\n")
        
        return {
            'round': self.current_round,
            'strategy': self.current_strategy,
            'assessment': assessment
        }


def run_intelligent_fl_simulation(
    num_nodes=5,
    num_malicious=1,
    num_rounds=15
):
    """
    Run FL with LLM-based intelligent coordination.
    """
    logger.info("\n" + "🤖"*35)
    logger.info("INTELLIGENT FL SIMULATION (LLM-POWERED)")
    logger.info("🤖"*35 + "\n")
    
    # Load data
    logger.info("Loading data...")
    data = np.load('data/processed/cicddos2019_full_processed.npz')
    X, y = data['X'], data['y']
    
    # Apply feature selection
    with open('data/processed/cicddos2019_full_processed_feature_selection.pkl', 'rb') as f:
        results = pickle.load(f)
    
    X = X[:, results['ensemble']['indices']]
    logger.info(f"Using 40 selected features")
    
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
    
    # Model builder
    def build_model():
        model = CNNBiLSTMModel(
            input_shape=X_train_r.shape[1:],
            num_classes=len(np.unique(y)),
            cnn_filters=(64, 128),
            lstm_units=(64, 32),
            dropout_rate=0.5
        )
        return model.model
    
    # Initialize intelligent server
    global_model = build_model()
    fl_server = IntelligentFLServer(global_model, num_rounds)
    
    # Initialize nodes
    fl_nodes = {}
    malicious_nodes = set()
    
    for i in range(num_nodes):
        node_id = f"node_{i+1}"
        is_malicious = i < num_malicious
        
        X_node, y_node = node_datasets[i]
        
        if is_malicious:
            y_node = MaliciousNodeSimulator.label_flip_attack(y_node, flip_ratio=0.3)
            malicious_nodes.add(node_id)
            logger.warning(f"⚠ {node_id}: MALICIOUS")
        
        node = FLNode(
            node_id=node_id,
            local_data=(X_node, y_node),
            model_builder_fn=build_model,
            epochs_per_round=5,
            batch_size=64
        )
        
        # Register
        credentials = fl_server.register_node_with_intelligence(node_id, len(X_node))
        
        fl_nodes[node_id] = {
            'node': node,
            'api_key': credentials.api_key,
            'is_malicious': is_malicious
        }
    
    logger.info(f"\n✓ {num_nodes} nodes initialized ({num_malicious} malicious)")
    
    # Run FL rounds
    for round_num in range(1, num_rounds + 1):
        # Get global weights
        global_weights = fl_server.get_global_model_weights()
        
        # Collect updates
        local_updates = {}
        
        for node_id, node_data in fl_nodes.items():
            node = node_data['node']
            api_key = node_data['api_key']
            is_malicious = node_data['is_malicious']
            
            # Train
            update = node.participate_in_round(global_weights, verbose=0)
            
            # Occasional attacks from malicious nodes
            if is_malicious and np.random.rand() > 0.5:
                update['weights'] = MaliciousNodeSimulator.gaussian_noise_attack(
                    update['weights'], noise_scale=0.3
                )
            
            update['api_key'] = api_key
            local_updates[node_id] = update
        
        # Intelligent aggregation
        round_summary = fl_server.run_intelligent_round(local_updates)
        
        # Periodic evaluation
        if round_num % 5 == 0:
            logger.info(f"\n📊 Evaluating global model...")
            test_results = global_model.evaluate(X_test_r, y_test, verbose=0)
            logger.info(f"  Test Accuracy: {test_results[1]:.4f}")
    
    # Final evaluation
    logger.info("\n" + "="*70)
    logger.info("FINAL EVALUATION")
    logger.info("="*70)
    
    final_results = global_model.evaluate(X_test_r, y_test, verbose=0)
    logger.info(f"\nFinal Accuracy: {final_results[1]:.4f}")
    logger.info(f"Final Loss: {final_results[0]:.4f}")
    
    # LLM Summary
    fl_server.agent.summary()
    
    # System health report
    system_metrics = {
        'final_accuracy': float(final_results[1]),
        'final_loss': float(final_results[0]),
        'rounds_completed': num_rounds,
        'nodes_total': num_nodes,
        'malicious_nodes': num_malicious
    }
    
    fl_server.agent.generate_health_report(system_metrics)
    
    logger.info("\n" + "✅"*35)
    logger.info("INTELLIGENT FL COMPLETE!")
    logger.info("✅"*35)
    
    return fl_server, fl_nodes, global_model


def main():
    """Run intelligent FL simulation"""
    
    # Configuration
    NUM_NODES = 5
    NUM_MALICIOUS = 1
    NUM_ROUNDS = 15  # Fewer rounds for faster testing
    
    logger.info("="*70)
    logger.info("LLM-Based Intelligent FL Simulation")
    logger.info("="*70)
    logger.info(f"Nodes: {NUM_NODES} ({NUM_MALICIOUS} malicious)")
    logger.info(f"Rounds: {NUM_ROUNDS}")
    logger.info("="*70 + "\n")
    
    fl_server, fl_nodes, model = run_intelligent_fl_simulation(
        num_nodes=NUM_NODES,
        num_malicious=NUM_MALICIOUS,
        num_rounds=NUM_ROUNDS
    )
    
    return fl_server, fl_nodes, model


if __name__ == "__main__":
    main()
