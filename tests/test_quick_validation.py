"""
Simple functional validation - no training, just component checks
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np

print("\n" + "="*60)
print("Quick Component Test (No Training)")
print("="*60 + "\n")

# Test 1: Imports
print("Test 1: Core imports...")
try:
    from projects.shared_libs import CNNBiLSTMModel, TransformerModel
    from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator
    from projects.shared_libs.simple_fabric_client import SimpleFabricClient
    from projects.shared_libs.trust_manager import TrustManager
    print("✓ All imports successful")
except Exception as e:
    print(f"✗ Import failed: {e}")
    exit(1)

# Test 2: Byzantine Defense (No Training)
print("\nTest 2: Byzantine Defense Algorithm...")
try:
    # 5 weight updates
    updates = [
        [np.random.randn(10, 5) * 0.1] for _ in range(3)  # Honest
    ] + [
        [np.random.randn(10, 5) * 100.0] for _ in range(2)  # Malicious
    ]
    
    # Test all aggregation methods
    krum_result = ByzantineRobustAggregator.krum(updates, num_byzantine=2)
    print(f"  ✓ KRUM: max={np.max(np.abs(krum_result[0])):.2f}")
    
    trimmed_result = ByzantineRobustAggregator.trimmed_mean(updates, trim_ratio=0.2)
    print(f"  ✓ Trimmed Mean: max={np.max(np.abs(trimmed_result[0])):.2f}")
    
    median_result = ByzantineRobustAggregator.median(updates)
    print(f"  ✓ Median: max={np.max(np.abs(median_result[0])):.2f}")
    
except Exception as e:
    print(f"✗ Byzantine defense failed: {e}")
    exit(1)

# Test 3: Trust Manager
print("\nTest 3: Trust Management...")
try:
    tm = TrustManager(min_trust_threshold=0.5)
    
    # Register nodes
    for i in range(5):
        tm.register_node(f"node_{i}", {"type": "test"})
    
    # Update trust scores
    tm.trust_scores["node_0"].update(0.1, "Good behavior")
    tm.trust_scores["node_1"].update(-0.3, "Suspicious")
    
    # Get trusted nodes
    trusted = tm.get_trusted_nodes()
    print(f"  ✓ Trust manager working ({len(trusted)} trusted nodes)")
    
except Exception as e:
    print(f"✗ Trust manager failed: {e}")
    exit(1)

# Test 4: Blockchain Client (Simulation)
print("\nTest 4: Blockchain (Simulation Mode)...")
try:
    bc = SimpleFabricClient()
    
    # Log transactions
    for i in range(10):
        tx = bc.log_model_update(
            node_id=f"node_{i % 3}",
            model_weights=[np.random.randn(5, 3)],
            round_number=i // 3
        )
    
    # Query
    records = bc.query_records_by_round(0)
    print(f"  ✓ Blockchain logging: {len(records)} records in round 0")
    
    # Aggregation log
    tx_agg = bc.log_aggregation(
        round_number=0,
        global_model_hash="test123",
        participating_nodes=["node_0", "node_1", "node_2"]
    )
    print(f"  ✓ Aggregation logged: {tx_agg[:16]}...")
    
except Exception as e:
    print(f"✗ Blockchain failed: {e}")
    exit(1)

# Test 5: Model Architecture (No Training)
print("\nTest 5: Model Architecture...")
try:
    # Just check model creation
    from tensorflow.keras.models import Model
    
    cnn = CNNBiLSTMModel(
        input_shape=(10, 40),
        num_classes=2,
        cnn_filters=(32, 16),
        lstm_units=(16,)
    ).model
    
    assert isinstance(cnn, Model)
    print(f"  ✓ CNN-BiLSTM: {cnn.count_params():,} parameters")
    
    transformer = TransformerModel(
        input_shape=(10, 40),
        num_classes=2,
        head_size=32,
        num_heads=2,
        num_transformer_blocks=1
    ).model
    
    assert isinstance(transformer, Model)
    print(f"  ✓ Transformer: {transformer.count_params():,} parameters")
    
except Exception as e:
    print(f"✗ Model creation failed: {e}")
    exit(1)

# Test 6: Multi-Agent (Mock Mode)
print("\nTest 6: Multi-Agent System...")
try:
    from projects.shared_libs.multi_agent_llm import MultiAgentCoordinator
    
    coordinator = MultiAgentCoordinator(enable_auto_response=False)
    
    round_data = {
        'round_number': 5,
        'participating_nodes': 5,
        'trust_scores': {f'n{i}': 0.9 for i in range(5)},
        'anomalies_detected': []
    }
    
    decisions = coordinator.coordinate_fl_round(round_data)
    
    assert 'aggregation_strategy' in decisions
    print(f"  ✓ Multi-agent coordination: {decisions['aggregation_strategy']}")
    
except Exception as e:
    print(f"✗ Multi-agent failed: {e}")
    exit(1)

# Summary
print("\n" + "="*60)
print("Test Summary")
print("="*60)
print("✅ All 6 component tests passed!")
print("")
print("Validated Components:")
print("  ✓ Byzantine Defense (KRUM, Trimmed Mean, Median)")
print("  ✓ Trust Management")
print("  ✓ Blockchain Integration")
print("  ✓ Model Architectures (CNN-BiLSTM, Transformer)")
print("  ✓ Multi-Agent Coordination")
print("")
print("🎉 Humanized code is fully functional!")
print("="*60 + "\n")
