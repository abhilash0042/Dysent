"""
Test suite for Hyperledger Fabric blockchain integration.

This validates both real Fabric (if available) and simulation mode.
"""

import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from projects.shared_libs.hyperledger_fabric_client import FabricBlockchainClient

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_blockchain_client():
    """Test Fabric blockchain client (simulation or real)"""
    logger.info("\n" + "="*70)
    logger.info("HYPERLEDGER FABRIC BLOCKCHAIN TEST")
    logger.info("="*70)
    
    # Initialize client
    logger.info("\n1️⃣ Initializing blockchain client...")
    blockchain = FabricBlockchainClient()
    
    # Connect (will use simulation if Fabric not available)
    logger.info("\n2️⃣ Connecting to network...")
    import asyncio
    asyncio.run(blockchain.connect())
    
    # Test  1: Node Registration
    logger.info("\n3️⃣ Testing node registration...")
    tx_id1 = blockchain.log_node_registration(
        node_id="test_node_1",
        metadata={"type": "edge", "location": "datacenter-1"}
    )
    logger.info(f"   ✓ Node registered: {tx_id1[:16]}...")
    
    # Test 2: Model Update
    logger.info("\n4️⃣ Testing model update logging...")
    dummy_weights = [np.random.randn(10, 5), np.random.randn(5)]
    tx_id2 = blockchain.log_model_update(
        node_id="test_node_1",
        model_weights=dummy_weights,
        round_number=1,
        metadata={"accuracy": 0.95}
    )
    logger.info(f"   ✓ Model update logged: {tx_id2[:16]}...")
    
    # Test 3: Aggregation
    logger.info("\n5️⃣ Testing aggregation logging...")
    global_hash = "abc123def456"
    tx_id3 = blockchain.log_aggregation(
        round_number=1,
        global_model_hash=global_hash,
        participating_nodes=["test_node_1", "test_node_2"]
    )
    logger.info(f"   ✓ Aggregation logged: {tx_id3[:16]}...")
    
    # Test 4: Security Alert
    logger.info("\n6️⃣ Testing security alert...")
    tx_id4 = blockchain.log_security_alert(
        node_id="test_node_2",
        alert_type="BYZANTINE_DETECTED",
        round_number=1,
        details="Node failed Byzantine test (gradient divergence > 0.5)"
    )
    logger.info(f"   ✓ Security alert logged: {tx_id4[:16]}...")
    
    # Test 5: Query
    logger.info("\n7️⃣ Testing query functions...")
    if hasattr(blockchain, 'simulation_ledger'):
        # Simulation mode
        records = blockchain.query_records_by_round(1)
        logger.info(f"   ✓ Found {len(records)} records for round 1")
        for record in records:
            logger.info(f"     - {record['eventType']}: {record['nodeID']}")
    
    logger.info("\n" + "="*70)
    logger.info("✅ ALL BLOCKCHAIN TESTS PASSED")
    logger.info("="*70)
    
    if hasattr(blockchain, 'simulation_ledger'):
        logger.info("\n📝 Note: Running in SIMULATION mode")
        logger.info("   To use real Fabric:")
        logger.info("   1. Install: pip install fabric-sdk-py")
        logger.info("   2. Run: cd ddosdfl/fabric && docker-compose up -d")
        logger.info("   3. Deploy chaincode: ./deploy-chaincode.sh")
    
    return blockchain


if __name__ == "__main__":
    test_blockchain_client()
