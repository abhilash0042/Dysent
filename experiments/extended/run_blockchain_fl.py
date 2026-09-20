"""
Blockchain-Enhanced FL Experiment

Demonstrates FL with complete blockchain audit trail for:
- FL round logging
- Model update tracking  
- Trust score changes
- Anomaly detection
- Security events
- Immutable audit reports
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
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.blockchain_interface import Blockchain, SmartContract, AuditLogger
from projects.shared_libs.trust_manager import TrustManager
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator, MaliciousNodeSimulator
from projects.fl.aggregation_server import FederatedServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


def hash_model_weights(weights: list) -> str:
    """Generate hash of model weights for blockchain"""
    weights_str = str([w.tolist() for w in weights])
    return hashlib.sha256(weights_str.encode()).hexdigest()[:16]


def run_blockchain_fl(
    num_nodes: int = 5,
    num_rounds: int = 10,
    malicious_ratio: float = 0.2,
    data_tuple=None
):
    """
    Run FL with blockchain audit trail.
    
    Args:
        num_nodes: Number of FL nodes
        num_rounds: Number of FL rounds
        malicious_ratio: Fraction of malicious nodes
        data_tuple: Pre-loaded data
        
    Returns:
        Results with blockchain audit
    """
    logger.info(f"\n{'='*70}")
    logger.info("BLOCKCHAIN-ENHANCED FEDERATED LEARNING")
    logger.info(f"{'='*70}")
    
    X_train_r, X_test_r, y_train, y_test, build_model = data_tuple
    
    # Initialize blockchain system
    blockchain = Blockchain()
    smart_contract = SmartContract(blockchain)
    audit_logger = AuditLogger(blockchain, smart_contract)
    
    logger.info("\n✓ Blockchain system initialized")
    logger.info(f"  Genesis block: {blockchain.chain[0].hash[:16]}...")
    
    # Fixed seed
    np.random.seed(42)
    
    # Split data
    indices = np.random.permutation(len(X_train_r))
    splits = np.array_split(indices, num_nodes)
    node_datasets = [(X_train_r[split], y_train[split]) for split in splits]
    
    num_malicious = int(num_nodes * malicious_ratio)
    
    # Server with blockchain integration
    global_model = build_model()
    
    class BlockchainFLServer(FederatedServer):
        def __init__(self, global_model, num_rounds, blockchain, smart_contract, audit_logger):
            super().__init__(global_model, num_rounds)
            self.blockchain = blockchain
            self.smart_contract = smart_contract
            self.audit = audit_logger
            self.trust_manager = TrustManager(min_trust_threshold=0.5)
            self.round_accuracies = []
        
        def run_blockchain_round(self, local_updates, X_test, y_test):
            self.current_round += 1
            
            # Log FL round start
            participating_nodes = list(local_updates.keys())
            self.audit.log_fl_round_start(
                round_number=self.current_round,
                participating_nodes=participating_nodes
            )
            
            # Authenticate & validate
            authenticated_updates = {}
            for node_id, update in local_updates.items():
                api_key = update.get('api_key', '')
                if self.trust_manager.authenticate_node(node_id, api_key):
                    can_part, _ = self.trust_manager.can_participate(node_id, self.current_round)
                    if can_part:
                        authenticated_updates[node_id] = update
            
            # Validate updates
            validated_updates = {}
            for node_id, update in authenticated_updates.items():
                is_valid, analysis = self.trust_manager.validate_model_update(
                    node_id, update['weights']
                )
                
                if is_valid:
                    validated_updates[node_id] = update
                    
                    # Record participation on blockchain
                    model_hash = hash_model_weights(update['weights'])
                    self.smart_contract.record_participation(
                        node_id=node_id,
                        round_number=self.current_round,
                        model_update_hash=model_hash,
                        metrics={'loss': float(update.get('loss', 0))}
                    )
                else:
                    # Log anomaly on blockchain
                    self.audit.log_anomaly_detected(
                        node_id=node_id,
                        anomaly_type='invalid_update',
                        severity='high',
                        details=analysis
                    )
                    
                    # Update trust score
                    current_trust = self.trust_manager.get_trust_score(node_id)
                    new_trust = max(0.0, current_trust - 0.1)
                    self.smart_contract.update_trust_score(
                        node_id=node_id,
                        new_trust_score=new_trust,
                        reason='Anomaly detected in model update'
                    )
                    
                    # Quarantine if trust too low
                    if new_trust < 0.3:
                        self.smart_contract.quarantine_node(
                            node_id=node_id,
                            reason='Trust score below threshold'
                        )
            
            # Aggregate with Byzantine defense
            weights_list = [upd['weights'] for upd in validated_updates.values()]
            data_sizes = [self.registered_nodes[nid]['data_size'] for nid in validated_updates.keys()]
            
            if len(validated_updates) >= 3:
                aggregated = ByzantineRobustAggregator.trimmed_mean(weights_list)
            else:
                aggregated = self.federated_averaging(weights_list, data_sizes)
            
            self.global_model.set_weights(aggregated)
            
            # Evaluate
            results = self.global_model.evaluate(X_test, y_test, verbose=0)
            self.round_accuracies.append(float(results[1]))
            
            # Log FL round completion
            global_hash = hash_model_weights(aggregated)
            self.audit.log_fl_round_complete(
                round_number=self.current_round,
                global_model_hash=global_hash,
                metrics={
                    'accuracy': float(results[1]),
                    'loss': float(results[0]),
                    'validated_nodes': len(validated_updates)
                }
            )
            
            if self.current_round % 5 == 0:
                logger.info(
                    f"  Round {self.current_round}: Acc={results[1]:.4f}, "
                    f"Valid nodes={len(validated_updates)}/{len(local_updates)}"
                )
            
            return results
    
    fl_server = BlockchainFLServer(
        global_model, num_rounds, blockchain, smart_contract, audit_logger
    )
    
    # Initialize nodes
    fl_nodes = {}
    for i in range(num_nodes):
        node_id = f"node_{i+1}"
        is_malicious = i < num_malicious
        
        # Register node on blockchain
        smart_contract.register_node(
            node_id=node_id,
            node_info={
                'type': 'malicious' if is_malicious else 'honest',
                'data_size': len(node_datasets[i][0])
            }
        )
        
        X_node, y_node = node_datasets[i]
        
        if is_malicious:
            y_node = MaliciousNodeSimulator.label_flip_attack(y_node, flip_ratio=0.3)
        
        node = FLNode(
            node_id=node_id,
            local_data=(X_node, y_node),
            model_builder_fn=build_model,
            epochs_per_round=3,
            batch_size=64
        )
        
        credentials = fl_server.trust_manager.register_node(node_id, {'data_size': len(X_node)})
        fl_server.register_node(node_id, len(X_node))
        
        fl_nodes[node_id] = {
            'node': node,
            'api_key': credentials.api_key,
            'is_malicious': is_malicious
        }
    
    logger.info(f"\n✓ {num_nodes} nodes registered on blockchain")
    logger.info(f"  Malicious: {num_malicious}, Honest: {num_nodes - num_malicious}")
    
    # Run FL rounds
    logger.info(f"\n{'='*70}")
    logger.info("STARTING BLOCKCHAIN FL")
    logger.info(f"{'='*70}\n")
    
    for round_num in range(1, num_rounds + 1):
        global_weights = fl_server.get_global_model_weights()
        
        local_updates = {}
        for node_id, node_data in fl_nodes.items():
            node = node_data['node']
            api_key = node_data['api_key']
            is_malicious = node_data['is_malicious']
            
            update = node.participate_in_round(global_weights, verbose=0)
            
            if is_malicious and np.random.rand() > 0.5:
                update['weights'] = MaliciousNodeSimulator.gaussian_noise_attack(
                    update['weights'], noise_scale=0.2
                )
            
            update['api_key'] = api_key
            local_updates[node_id] = update
        
        fl_server.run_blockchain_round(local_updates, X_test_r, y_test)
    
    # Final evaluation
    final_results = global_model.evaluate(X_test_r, y_test, verbose=0)
    
    # Blockchain verification
    is_valid = blockchain.is_chain_valid()
    blockchain_summary = blockchain.get_summary()
    
    logger.info(f"\n{'='*70}")
    logger.info("BLOCKCHAIN FL COMPLETE")
    logger.info(f"{'='*70}")
    logger.info(f"\n✓ Final Accuracy: {final_results[1]:.4f}")
    logger.info(f"✓ Blockchain Valid: {is_valid}")
    logger.info(f"✓ Total Blocks: {blockchain_summary['total_blocks']}")
    logger.info(f"✓ Block Types: {blockchain_summary['block_types']}")
    
    # Generate audit report
    audit_report = audit_logger.generate_audit_report()
    
    logger.info(f"\n📋 Audit Report:")
    logger.info(f"  FL Rounds: {len(audit_report['fl_rounds'])}")
    logger.info(f"  Security Events: {len(audit_report['security_events'])}")
    logger.info(f"  Trust Updates: {len(audit_report['trust_updates'])}")
    logger.info(f"  Quarantines: {len(audit_report['quarantines'])}")
    
    return {
        'final_accuracy': float(final_results[1]),
        'final_loss': float(final_results[0]),
        'blockchain_valid': is_valid,
        'blockchain_summary': blockchain_summary,
        'audit_report': audit_report,
        'round_accuracies': fl_server.round_accuracies
    }


def run_blockchain_experiment():
    """Run complete blockchain FL experiment"""
    
    logger.info(f"\n{'='*70}")
    logger.info("BLOCKCHAIN AUDIT TRAIL EXPERIMENT")
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
    
    # Run blockchain FL
    results = run_blockchain_fl(
        num_nodes=5,
        num_rounds=10,
        malicious_ratio=0.2,
        data_tuple=data_tuple
    )
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"results/blockchain_experiment_{timestamp}.json"
    
    import os
    os.makedirs('results', exist_ok=True)
    
    # Convert audit report for JSON serialization
    report_json = {
        **results,
        'timestamp': timestamp
    }
    
    with open(results_file, 'w') as f:
        json.dump(report_json, f, indent=2)
    
    logger.info(f"\n✓ Results saved to: {results_file}")
    
    return results


def main():
    """Run blockchain experiment"""
    
    logger.info("Starting Blockchain Audit Trail experiment...")
    
    results = run_blockchain_experiment()
    
    logger.info(f"\n{'='*70}")
    logger.info("✅ BLOCKCHAIN EXPERIMENT COMPLETE!")
    logger.info(f"{'='*70}")
    logger.info(f"\n🔗 Blockchain Features Demonstrated:")
    logger.info(f"  ✓ Immutable FL round logging")
    logger.info(f"  ✓ Model update tracking")
    logger.info(f"  ✓ Trust score auditing")
    logger.info(f"  ✓ Anomaly detection logging")
    logger.info(f"  ✓ Security event recording")
    logger.info(f"  ✓ Tamper-proof verification")
    logger.info(f"  ✓ Comprehensive audit reports")
    
    return results


if __name__ == "__main__":
    main()
