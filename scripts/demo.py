"""
Simple Demo: Privacy-Preserving DDoS Detection System

Demonstrates the core components working together:
1. Data loading and preprocessing
2. CNN-BiLSTM model creation
3. Zero-trust security
4. Simulated blockchain
5. Local training
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


import sys
import logging
import numpy as np
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add projects to path
sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs.data_processor import (
    DatasetLoader, FeatureExtractor, DataPartitioner, split_data
)
from projects.shared_libs.cnn_bilstm_model import (
    CNNBiLSTMModel, ModelTrainer, ModelEvaluator
)
from projects.shared_libs.trust_manager import TrustManager
from projects.shared_libs.blockchain_interface import (
    Blockchain, SmartContract, AuditLogger
)
from projects.fl_node.local_trainer import LocalTrainer


def demo_data_processing():
    """Demonstrate data loading and preprocessing"""
    logger.info("="*70)
    logger.info("DEMO 1: Data Processing")
    logger.info("="*70)
    
    # For demo, create synthetic data (replace with real dataset in production)
    logger.info("Creating synthetic traffic data for demonstration...")
    
    # Simulate 1000 network flow samples with 40 features
    num_samples = 1000
    num_features = 40
    
    X_synthetic = np.random.randn(num_samples, num_features)
    y_synthetic = np.random.randint(0, 2, num_samples)  # Binary: 0=benign, 1=DDoS
    
    logger.info(f"Synthetic data shape: X={X_synthetic.shape}, y={y_synthetic.shape}")
    logger.info(f"Class distribution: {np.bincount(y_synthetic)}")
    
    # Split data
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X_synthetic, y_synthetic,
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15
    )
    
    # Partition for FL nodes
    partitioner = DataPartitioner(num_nodes=3, iid=True)
    node_datasets = partitioner.partition(X_train, y_train)
    
    logger.info(f"Created {len(node_datasets)} FL node datasets")
    
    return node_datasets, (X_val, y_val), (X_test, y_test)


def demo_model_creation():
    """Demonstrate CNN-BiLSTM model creation"""
    logger.info("\n" + "="*70)
    logger.info("DEMO 2: CNN-BiLSTM Model Creation")
    logger.info("="*70)
    
    # Create model
    model = CNNBiLSTMModel(
        input_shape=(10, 4),  # 10 timesteps, 4 features per timestep
        num_classes=2,
        cnn_filters=(32, 64),
        lstm_units=(32, 16),
        dropout_rate=0.3,
        learning_rate=0.001
    )
    
    logger.info("Model created successfully!")
    model.summary()
    
    return model


def demo_zero_trust():
    """Demonstrate zero-trust security"""
    logger.info("\n" + "="*70)
    logger.info("DEMO 3: Zero-Trust Security")
    logger.info("="*70)
    
    trust_mgr = TrustManager(min_trust_threshold=0.5)
    
    # Register 3 nodes
    nodes = []
    for i in range(3):
        node_id = f"node-{i+1:03d}"
        credentials = trust_mgr.register_node(
            node_id,
            {"name": f"Edge Node {i+1}", "location": f"Region {i+1}"}
        )
        nodes.append((node_id, credentials))
        logger.info(f"Registered {node_id} with API key: {credentials.api_key[:16]}...")
    
    # Test authentication
    node_id, credentials = nodes[0]
    auth_result = trust_mgr.authenticate_node(node_id, credentials.api_key)
    logger.info(f"Authentication result for {node_id}: {auth_result}")
    
    # Check participation eligibility
    can_participate, reason = trust_mgr.can_participate(node_id, round_number=1)
    logger.info(f"Can {node_id} participate? {can_participate} - {reason}")
    
    # Get all nodes status
    logger.info("\nAll nodes status:")
    logger.info(f"Trusted nodes: {trust_mgr.get_trusted_nodes()}")
    
    return trust_mgr, nodes


def demo_blockchain():
    """Demonstrate blockchain audit trail"""
    logger.info("\n" + "="*70)
    logger.info("DEMO 4: Blockchain Audit Trail")
    logger.info("="*70)
    
    blockchain = Blockchain()
    smart_contract = SmartContract(blockchain)
    audit_logger = AuditLogger(blockchain, smart_contract)
    
    # Register nodes
    for i in range(3):
        node_id = f"node-{i+1:03d}"
        smart_contract.register_node(node_id, {"name": f"Edge Node {i+1}"})
    
    # Simulate FL rounds
    for round_num in range(1, 4):
        participating_nodes = [f"node-{i+1:03d}" for i in range(3)]
        
        # Log round start
        audit_logger.log_fl_round_start(round_num, participating_nodes)
        
        # Simulate participation
        for node_id in participating_nodes:
            smart_contract.record_participation(
                node_id,
                round_num,
                model_update_hash=f"hash_{node_id}_r{round_num}",
                metrics={"accuracy": 0.85 + round_num * 0.03}
            )
        
        # Log round complete
        audit_logger.log_fl_round_complete(
            round_num,
            global_model_hash=f"global_model_r{round_num}",
            metrics={"accuracy": 0.87 + round_num * 0.03}
        )
    
    # Verify blockchain integrity
    is_valid = blockchain.is_chain_valid()
    logger.info(f"\nBlockchain integrity: {'✅ VALID' if is_valid else '❌ INVALID'}")
    
    # Get summary
    summary = blockchain.get_summary()
    logger.info(f"\nBlockchain summary:")
    logger.info(f"  Total blocks: {summary['total_blocks']}")
    logger.info(f"  Block types: {summary['block_types']}")
    
    # Generate audit report
    report = audit_logger.generate_audit_report()
    logger.info(f"\nAudit report:")
    logger.info(f"  Total events: {report['total_events']}")
    logger.info(f"  FL rounds completed: {len(report['fl_rounds'])}")
    
    return blockchain, smart_contract, audit_logger


def demo_local_training(model, node_datasets):
    """Demonstrate local training on FL node"""
    logger.info("\n" + "="*70)
    logger.info("DEMO 5: Local Training on FL Node")
    logger.info("="*70)
    
    # Get data for first node
    X_node, y_node = node_datasets[0]
    
    # Reshape for CNN-BiLSTM (timesteps=10, features_per_timestep=4)
    ModelTrainer_instance = ModelTrainer(model)
    X_node_reshaped, y_node = ModelTrainer_instance.prepare_data_for_training(
        X_node, y_node, timesteps=10
    )
    
    # Split into train/val for this node
    split_idx = int(0.8 * len(X_node_reshaped))
    X_train_node = X_node_reshaped[:split_idx]
    y_train_node = y_node[:split_idx]
    X_val_node = X_node_reshaped[split_idx:]
    y_val_node = y_node[split_idx:]
    
    # Create local trainer
    local_trainer = LocalTrainer(
        model=model.get_model(),
        node_id="node-001"
    )
    
    # Train locally for 3 epochs
    metrics = local_trainer.train_local_model(
        X_train_node, y_train_node,
        X_val_node, y_val_node,
        epochs=3,
        batch_size=16,
        round_number=1
    )
    
    logger.info(f"\nTraining completed!")
    logger.info(f"Final metrics: {metrics}")
    
    # Get model hash
    model_hash = local_trainer.compute_model_hash()
    logger.info(f"Model hash (for blockchain): {model_hash[:32]}...")
    
    return local_trainer, model_hash


def main():
    """Run all demos"""
    logger.info("\n" + "🚀"*35)
    logger.info("Privacy-Preserving DDoS Detection System - Component Demo")
    logger.info("🚀"*35 + "\n")
    
    try:
        # Demo 1: Data Processing
        node_datasets, val_data, test_data = demo_data_processing()
        
        # Demo 2: Model Creation
        model = demo_model_creation()
        
        # Demo 3: Zero-Trust Security
        trust_mgr, nodes = demo_zero_trust()
        
        # Demo 4: Blockchain
        blockchain, smart_contract, audit_logger = demo_blockchain()
        
        # Demo 5: Local Training
        local_trainer, model_hash = demo_local_training(model, node_datasets)
        
        # Integration demo: Validate model update with trust manager
        logger.info("\n" + "="*70)
        logger.info("INTEGRATION DEMO: Zero-Trust Model Validation")
        logger.info("="*70)
        
        node_id, credentials = nodes[0]
        model_weights = local_trainer.get_model_weights()
        
        is_valid, analysis = trust_mgr.validate_model_update(node_id, model_weights)
        
        logger.info(f"\nModel update validation for {node_id}:")
        logger.info(f"  Valid: {is_valid}")
        logger.info(f"  Anomaly score: {analysis['anomaly_score']:.3f}")
        logger.info(f"  Anomalies detected: {analysis['anomalies']}")
        logger.info(f"  Trust score after validation: {trust_mgr.get_trust_score(node_id):.3f}")
        
        # Log to blockchain if valid
        if is_valid:
            smart_contract.record_participation(
                node_id,
                round_number=1,
                model_update_hash=model_hash,
                metrics={"accuracy": 0.89}
            )
            logger.info(f"\n✅ Model update logged to blockchain")
        
        logger.info("\n" + "✅"*35)
        logger.info("ALL DEMOS COMPLETED SUCCESSFULLY!")
        logger.info("✅"*35 + "\n")
        
        logger.info("\n" + "="*70)
        logger.info("NEXT STEPS:")
        logger.info("="*70)
        logger.info("1. Download CICDDoS2019 or NSLKDD dataset")
        logger.info("2. Set OPENROUTER_API_KEY in .env file")
        logger.info("3. Implement FL node client and aggregation server")
        logger.info("4. Run full federated learning experiment")
        logger.info("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"\n❌ Error during demo: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
