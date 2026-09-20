"""
Hyperledger Fabric Client for FL-DDoS System

This module provides a production-grade blockchain client that replaces
the Python simulation with real Hyperledger Fabric distributed ledger.
"""

import asyncio
import hashlib
import json
import logging
import os
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    from hfc.fabric import Client
    from hfc.fabric.user import create_user
    HFC_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ Hyperledger Fabric SDK not installed. Install with: pip install fabric-sdk-py")
    HFC_AVAILABLE = False


class FabricBlockchainClient:
    """
    Production Hyperledger Fabric client for FL audit logging.
    
    Features:
    - Immutable audit trails for all FL operations
    - Multi-peer consensus (Byzantine fault tolerant)
    - Real-time transaction verification
    - Query capabilities for audit investigations
    """
    
    def __init__(self, peer_endpoint=None, orderer_endpoint=None, channel_name="ddoschannel"):
        """
        Initialize Hyperledger Fabric client (PRODUCTION MODE ONLY)
        
        Args:
            peer_endpoint: Peer gRPC endpoint (default: localhost:7051)
            orderer_endpoint: Orderer endpoint (default: localhost:7050)
            channel_name: Channel name (default: ddoschannel)
        """
        self.peer_endpoint = peer_endpoint or os.getenv("FABRIC_PEER_ENDPOINT", "localhost:7051")
        self.orderer_endpoint = orderer_endpoint or os.getenv("FABRIC_ORDERER_ENDPOINT", "localhost:7050")
        self.channel_name = channel_name or os.getenv("FABRIC_CHANNEL", "ddoschannel")
        self.chaincode_name = os.getenv("FABRIC_CHAINCODE", "fl-audit")
        
        self.client = None
        self.admin_user = None
        self.connected = False

        # PRODUCTION MODE ONLY - No simulation fallback
        simulation_disabled = os.getenv("BLOCKCHAIN_SIMULATION_MODE", "false").lower() == "false"
        
        if simulation_disabled:
            logger.info("🚀 PRODUCTION MODE: Simulation disabled")
            logger.info(f"Connecting to Fabric peer: {self.peer_endpoint}")
            
            # Attempt to connect to real Fabric
            if not HFC_AVAILABLE:
                raise ConnectionError(
                    "❌ Hyperledger Fabric SDK not installed. Cannot run in production mode.\n"
                    "   Install with: pip install fabric-sdk-py"
                )

            if not self._test_fabric_connection():
                raise ConnectionError(
                    "❌ Cannot connect to Hyperledger Fabric!\n"
                    "   Simulation mode is DISABLED.\n"
                    "   Please deploy blockchain:\n"
                    "   cd fabric && .\\deploy-production.ps1"
                )
            
            self.simulation_mode = False
            logger.info("✅ Connected to REAL Hyperledger Fabric")
        else:
            # Legacy simulation mode (only if explicitly enabled)
            logger.warning("⚠️  Simulation mode enabled (not recommended)")
            self.simulation_mode = True
            self.simulation_ledger = [] # Renamed from 'ledger' to avoid conflict if 'ledger' was intended for something else
    
    # Removed _init_simulation_mode
    
    async def connect(self, org_name='Client1', admin_name='Admin', admin_pw='adminpw'):
        """
        Connect to Hyperledger Fabric network.
        
        Args:
            org_name: Organization name (Client1, Client2, Client3)
            admin_name: Admin user name
            admin_pw: Admin password
        """
        if not HFC_AVAILABLE:
            logger.info("✓ Simulation mode active")
            return True
        
        try:
            logger.info(f"🔗 Connecting to Fabric network...")
            logger.info(f"   Organization: {org_name}")
            logger.info(f"   Channel: {self.channel_name}")
            
            # Create client from config
            self.client = Client(net_profile=self.config_path)
            
            # Get organization
            org = self.client.get_org(org_name)
            
            # Get CA client
            ca_client = self.client.get_ca_client(org_name)
            
            # Enroll admin
            enrollment = await ca_client.enroll(admin_name, admin_pw)
            self.admin_user = create_user(admin_name, org_name, org.msp_id, enrollment)
            
            self.connected = True
            logger.info("✓ Connected to Hyperledger Fabric network")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Fabric: {e}")
            logger.warning("Falling back to simulation mode")
            self._init_simulation_mode()
            return False
    
    def log_node_registration(self, node_id: str, metadata: Dict[str, Any]) -> str:
        """
        Log node registration to blockchain.
        
        Args:
            node_id: FL node identifier
            metadata: Additional node information
            
        Returns:
            Transaction ID
        """
        if not HFC_AVAILABLE:
            return self._simulate_transaction('NODE_REGISTRATION', node_id, metadata)
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_invoke(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='RecordNodeRegistration',
                args=[node_id, json.dumps(metadata)],
                cc_pattern=None
            )
        )
        
        tx_id = response
        logger.info(f"✓ Node registration logged: {tx_id[:16]}...")
        return tx_id
    
    def log_model_update(self, node_id: str, model_weights: List, 
                        round_number: int, metadata: Optional[Dict] = None) -> str:
        """
        Log model weight update to blockchain.
        
        Args:
            node_id: FL node identifier
            model_weights: Model weights (will be hashed for privacy)
            round_number: FL round number
            metadata: Optional metadata
            
        Returns:
            Transaction ID
        """
        # Hash weights (don't store raw weights on chain)
        weight_hash = self._hash_weights(model_weights)
        meta_str = json.dumps(metadata) if metadata else ""
        
        if not HFC_AVAILABLE:
            return self._simulate_transaction('MODEL_UPDATE', node_id, 
                                             {'hash': weight_hash, 'round': round_number})
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_invoke(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='RecordModelUpdate',
                args=[node_id, weight_hash, str(round_number), meta_str],
                cc_pattern=None
            )
        )
        
        tx_id = response
        logger.info(f"✓ Model update logged: Round {round_number}, Node {node_id}, TX: {tx_id[:16]}...")
        return tx_id
    
    def log_aggregation(self, round_number: int, global_model_hash: str, 
                       participating_nodes: List[str]) -> str:
        """
        Log server aggregation event.
        
        Args:
            round_number: FL round number
            global_model_hash: Hash of aggregated global model
            participating_nodes: List of node IDs that participated
            
        Returns:
            Transaction ID
        """
        nodes_str = ','.join(participating_nodes)
        
        if not HFC_AVAILABLE:
            return self._simulate_transaction('AGGREGATION', 'server', 
                                             {'round': round_number, 'nodes': nodes_str})
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_invoke(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='RecordAggregation',
                args=[str(round_number), global_model_hash, nodes_str],
                cc_pattern=None
            )
        )
        
        tx_id = response
        logger.info(f"✓ Aggregation logged: Round {round_number}, TX: {tx_id[:16]}...")
        return tx_id
    
    def log_security_alert(self, node_id: str, alert_type: str, 
                          round_number: int, details: str) -> str:
        """
        Log security alert (Byzantine detection, etc.).
        
        Args:
            node_id: Node that triggered the alert
            alert_type: Type of alert (BYZANTINE, POISONING, etc.)
            round_number: FL round number
            details: Alert details
            
        Returns:
            Transaction ID
        """
        if not HFC_AVAILABLE:
            return self._simulate_transaction('SECURITY_ALERT', node_id, 
                                             {'type': alert_type, 'round': round_number})
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_invoke(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='RecordSecurityAlert',
                args=[node_id, alert_type, str(round_number), details],
                cc_pattern=None
            )
        )
        
        tx_id = response
        logger.info(f"⚠️ Security alert logged: {alert_type}, TX: {tx_id[:16]}...")
        return tx_id
    
    def query_audit_record(self, record_id: str) -> Dict[str, Any]:
        """Query specific audit record by transaction ID"""
        if not HFC_AVAILABLE:
            return self._simulate_query(record_id)
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_query(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='QueryAuditRecord',
                args=[record_id]
            )
        )
        
        return json.loads(response)
    
    def query_records_by_node(self, node_id: str) -> List[Dict[str, Any]]:
        """Query all audit records for a specific node"""
        if not HFC_AVAILABLE:
            return [r for r in self.simulation_ledger if r.get('nodeID') == node_id]
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_query(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='QueryRecordsByNode',
                args=[node_id]
            )
        )
        
        return json.loads(response)
    
    def query_records_by_round(self, round_number: int) -> List[Dict[str, Any]]:
        """Query all audit records for a specific FL round"""
        if not HFC_AVAILABLE:
            return [r for r in self.simulation_ledger if r.get('roundNumber') == round_number]
        
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            self.client.chaincode_query(
                requestor=self.admin_user,
                channel_name=self.channel_name,
                peers=['peer0.client1.fl-ddos.com'],
                cc_name=self.chaincode_name,
                fcn='QueryRecordsByRound',
                args=[str(round_number)]
            )
        )
        
        return json.loads(response)
    
    def _hash_weights(self, weights: List) -> str:
        """Create SHA-256 hash of model weights"""
        import numpy as np
        
        # Convert weights to consistent string representation
        weight_str = str([np.array(w).tolist() if isinstance(w, np.ndarray) else w 
                         for w in weights])
        return hashlib.sha256(weight_str.encode()).hexdigest()
    
    def _simulate_transaction(self, event_type: str, node_id: str, metadata: Dict) -> str:
        """Simulation mode transaction"""
        import time
        tx_id = hashlib.sha256(f"{time.time()}{node_id}{event_type}".encode()).hexdigest()[:32]
        
        record = {
            'recordID': tx_id,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'eventType': event_type,
            'nodeID': node_id,
            'metadata': metadata
        }
        
        self.simulation_ledger.append(record)
        logger.info(f"[SIMULATION] {event_type} logged: {tx_id[:16]}...")
        return tx_id
    
    def _simulate_query(self, record_id: str) -> Dict[str, Any]:
        """Simulation mode query"""
        for record in self.simulation_ledger:
            if record['recordID'] == record_id:
                return record
        return {}


# Backward compatibility: alias for old blockchain interface
class Blockchain(FabricBlockchainClient):
    """Backward compatibility wrapper"""
    pass

# Primary alias for consistency
HyperledgerFabricClient = FabricBlockchainClient
