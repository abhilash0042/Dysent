"""
Standard Federated Learning Simulation

Demonstrates basic FL with FedAvg aggregation across 5 nodes.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pickle
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from projects.shared_libs import CNNBiLSTMModel
from projects.fl.aggregation_server import SimpleFLServer
from projects.fl.fl_node_client import FLNode
from scripts.data.load_cicddos import reshape_for_cnn_bilstm


def split_data_for_nodes(
    X: np.ndarray,
    y: np.ndarray,
    num_nodes: int = 5,
    iid: bool = True
) -> list:
    """
    Split data across FL nodes.
    
    Args:
        X: Features
        y: Labels
        num_nodes: Number of FL nodes to simulate
        iid: If True, random split (IID). If False, class-imbalanced (Non-IID)
        
    Returns:
        List of (X_node, y_node) tuples
    """
    logger.info("\n" + "="*70)
    logger.info(f"Splitting data for {num_nodes} FL nodes")
    logger.info(f"Distribution: {'IID (balanced)' if iid else 'Non-IID (imbalanced)'}")
    logger.info("="*70)
    
    if iid:
        # Random shuffle and split
        indices = np.random.permutation(len(X))
        splits = np.array_split(indices, num_nodes)
    else:
        # Non-IID: each node gets different class distributions
        # Simulate real-world: some orgs see more specific attacks
        splits = []
        classes = np.unique(y)
        
        # Assign classes to nodes with overlap
        for i in range(num_nodes):
            # Each node gets primary classes + some samples from all classes
            primary_classes = classes[i::num_nodes]  # Interleaved assignment
            
            # Get samples of primary classes (80%)
            primary_mask = np.isin(y, primary_classes)
            primary_indices = np.where(primary_mask)[0]
            
            # Get samples of all classes (20%)
            all_indices = np.random.choice(len(X), size=len(X)//num_nodes, replace=False)
            
            # Combine (80% primary, 20% diverse)
            node_indices = np.concatenate([
                np.random.choice(primary_indices, size=int(len(primary_indices)*0.8), replace=False),
                np.random.choice(all_indices, size=int(len(all_indices)*0.2), replace=False)
            ])
            
            splits.append(node_indices)
    
    # Create node datasets
    node_data = []
    for i, split_indices in enumerate(splits):
        X_node = X[split_indices]
        y_node = y[split_indices]
        node_data.append((X_node, y_node))
        
        logger.info(f"Node {i+1}: {len(X_node):,} samples, {len(np.unique(y_node))} classes")
    
    return node_data


def create_model_builder(input_shape, num_classes):
    """
    Factory function to create fresh model instances.
    
    Args:
        input_shape: Model input shape
        num_classes: Number of output classes
        
    Returns:
        Function that builds a new model
    """
    def build_model():
        model = CNNBiLSTMModel(
            input_shape=input_shape,
            num_classes=num_classes,
            cnn_filters=(64, 128),
            lstm_units=(64, 32),
            dropout_rate=0.5
        )
        return model.model  # Return Keras model
    
    return build_model


def run_federated_learning_simulation(
    num_nodes: int = 5,
    num_rounds: int = 20,
    epochs_per_round: int = 5,
    iid: bool = True,
    use_selected_features: bool = True
):
    """
    Run complete FL simulation.
    
    Args:
        num_nodes: Number of FL nodes to simulate
        num_rounds: Number of FL training rounds
        epochs_per_round: Local training epochs per round
        iid: IID vs Non-IID data distribution
        use_selected_features: Use feature selection results
    """
    logger.info("\n" + "🚀"*35)
    logger.info("FEDERATED LEARNING SIMULATION")
    logger.info("🚀"*35 + "\n")
    
    # ===== 1. Load Data and Features =====
    logger.info("Step 1: Loading data...")
    
    data_file = Path('data/processed/cicddos2019_full_processed.npz')
    data = np.load(data_file)
    X, y = data['X'], data['y']
    
    logger.info(f"Loaded: {X.shape[0]:,} samples, {X.shape[1]} features")
    
    # Apply feature selection if requested
    if use_selected_features:
        logger.info("\nApplying feature selection...")
        selection_file = Path('data/processed/cicddos2019_full_processed_feature_selection.pkl')
        
        with open(selection_file, 'rb') as f:
            results = pickle.load(f)
        
        # Use ensemble method (best performer: 98.92%)
        selected_indices = results['ensemble']['indices']
        X = X[:, selected_indices]
        
        logger.info(f"✓ Using {len(selected_indices)} selected features (ensemble method)")
    
    # Split into train/test
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    
    logger.info(f"Train: {len(X_train):,}, Test: {len(X_test):,}")
    
    # ===== 2. Reshape for CNN-BiLSTM =====
    logger.info("\nStep 2: Reshaping data for CNN-BiLSTM...")
    
    timesteps = 10
    X_train_r = reshape_for_cnn_bilstm(X_train, timesteps)
    X_test_r = reshape_for_cnn_bilstm(X_test, timesteps)
    
    logger.info(f"Reshaped: {X_train_r.shape}")
    
    # ===== 3. Split Data Across Nodes =====
    logger.info("\nStep 3: Creating node data splits...")
    
    node_datasets = split_data_for_nodes(X_train_r, y_train, num_nodes, iid=iid)
    
    # ===== 4. Initialize FL Server =====
    logger.info("\nStep 4: Initializing FL server...")
    
    # Create model builder
    model_builder = create_model_builder(
        input_shape=X_train_r.shape[1:],
        num_classes=len(np.unique(y))
    )
    
    # Create global model
    global_model = model_builder()
    
    # Initialize server
    fl_server = SimpleFLServer(
        global_model=global_model,
        num_rounds=num_rounds
    )
    
    # ===== 5. Initialize FL Nodes =====
    logger.info("\nStep 5: Initializing FL nodes...")
    
    fl_nodes = []
    for i, (X_node, y_node) in enumerate(node_datasets):
        node_id = f"node_{i+1}"
        
        node = FLNode(
            node_id=node_id,
            local_data=(X_node, y_node),
            model_builder_fn=model_builder,
            epochs_per_round=epochs_per_round,
            batch_size=64
        )
        
        fl_nodes.append(node)
        fl_server.register_node(node_id, len(X_node))
    
    logger.info(f"\n✓ {len(fl_nodes)} nodes initialized and registered")
    
    # ===== 6. Run FL Training Rounds =====
    logger.info("\n" + "="*70)
    logger.info("STARTING FEDERATED LEARNING")
    logger.info("="*70)
    
    for round_num in range(1, num_rounds + 1):
        logger.info(f"\n{'='*70}")
        logger.info(f"FL ROUND {round_num}/{num_rounds}")
        logger.info(f"{'='*70}")
        
        # Get global model weights
        global_weights = fl_server.get_global_weights()
        
        # Collect local updates
        local_updates = {}
        
        for node in fl_nodes:
            update = node.participate_in_round(
                global_weights=global_weights,
                verbose=0  # Silent training
            )
            local_updates[node.node_id] = update
        
        # Aggregate at server
        round_summary = fl_server.aggregate_and_update(local_updates)
        
        # Evaluate global model on test set every 5 rounds
        if round_num % 5 == 0:
            logger.info(f"\nEvaluating global model (Round {round_num})...")
            test_results = global_model.evaluate(X_test_r, y_test, verbose=0)
            logger.info(f"  Global Test Accuracy: {test_results[1]:.4f}")
            logger.info(f"  Global Test Loss: {test_results[0]:.4f}")
    
    # ===== 7. Final Evaluation =====
    logger.info("\n" + "="*70)
    logger.info("FINAL EVALUATION")
    logger.info("="*70)
    
    # Global model on test set
    final_results = global_model.evaluate(X_test_r, y_test, verbose=0)
    
    logger.info(f"\nFinal Global Model:")
    logger.info(f"  Test Accuracy: {final_results[1]:.4f}")
    logger.info(f"  Test Loss: {final_results[0]:.4f}")
    
    # ===== 8. Summary =====
    fl_server.summary()
    
    logger.info("\n" + "✅"*35)
    logger.info("FEDERATED LEARNING COMPLETE!")
    logger.info("✅"*35)
    
    # Save final global model
    save_path = Path("models/fl_global_model_final.keras")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    global_model.save(save_path)
    logger.info(f"\n✓ Final global model saved: {save_path}")
    
    return fl_server, fl_nodes, global_model


def main():
    """Run FL simulation with configurable parameters"""
    
    # Configuration
    NUM_NODES = 5  # Simulate 5 organizations
    NUM_ROUNDS = 20  # 20 FL training rounds
    EPOCHS_PER_ROUND = 5  # Each node trains for 5 epochs per round
    IID_DISTRIBUTION = True  # True = balanced, False = imbalanced
    USE_SELECTED_FEATURES = True  # Use 40 selected features (ensemble)
    
    # Run simulation
    fl_server, fl_nodes, global_model = run_federated_learning_simulation(
        num_nodes=NUM_NODES,
        num_rounds=NUM_ROUNDS,
        epochs_per_round=EPOCHS_PER_ROUND,
        iid=IID_DISTRIBUTION,
        use_selected_features=USE_SELECTED_FEATURES
    )
    
    return fl_server, fl_nodes, global_model


if __name__ == "__main__":
    main()
