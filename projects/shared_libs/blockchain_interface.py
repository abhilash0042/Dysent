"""
Simulated Blockchain Interface for DDoS Detection System

Lightweight, in-memory blockchain for audit trails and accountability
with minimal processing cost.
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Block:
    """Individual block in the blockchain"""
    index: int
    timestamp: float
    data: Dict[str, Any]
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    
    def calculate_hash(self) -> str:
        """Calculate block hash"""
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert block to dictionary"""
        return asdict(self)


class Blockchain:
    """Lightweight in-memory blockchain"""
    
    def __init__(self):
        """Initialize blockchain with genesis block"""
        self.chain: List[Block] = []
        self.pending_transactions: List[Dict[str, Any]] = []
        self.create_genesis_block()
        
        logger.info("Initialized blockchain")
    
    def create_genesis_block(self):
        """Create the first block in the chain"""
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            data={"message": "Genesis Block - DDoS Detection System"},
            previous_hash="0"
        )
        genesis_block.hash = genesis_block.calculate_hash()
        self.chain.append(genesis_block)
        
        logger.info(f"Created genesis block: {genesis_block.hash[:16]}...")
    
    def get_latest_block(self) -> Block:
        """Get the most recent block"""
        return self.chain[-1]
    
    def add_block(self, data: Dict[str, Any]) -> Block:
        """
        Add a new block to the chain
        
        Args:
            data: Block data
            
        Returns:
            Created block
        """
        latest_block = self.get_latest_block()
        
        new_block = Block(
            index=latest_block.index + 1,
            timestamp=time.time(),
            data=data,
            previous_hash=latest_block.hash
        )
        
        new_block.hash = new_block.calculate_hash()
        self.chain.append(new_block)
        
        logger.info(
            f"Added block #{new_block.index} | "
            f"Hash: {new_block.hash[:16]}... | "
            f"Type: {data.get('type', 'unknown')}"
        )
        
        return new_block
    
    def is_chain_valid(self) -> bool:
        """
        Validate the integrity of the blockchain
        
        Returns:
            True if chain is valid
        """
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Check if current hash is correct
            if current_block.hash != current_block.calculate_hash():
                logger.error(f"Block #{i} hash is invalid")
                return False
            
            # Check if previous hash matches
            if current_block.previous_hash != previous_block.hash:
                logger.error(f"Block #{i} previous hash doesn't match")
                return False
        
        return True
    
    def get_blocks_by_type(self, block_type: str) -> List[Block]:
        """
        Get all blocks of a specific type
        
        Args:
            block_type: Type of block (e.g., 'fl_round', 'security_event')
            
        Returns:
            List of matching blocks
        """
        return [
            block for block in self.chain
            if block.data.get('type') == block_type
        ]
    
    def get_blocks_by_node(self, node_id: str) -> List[Block]:
        """
        Get all blocks related to a specific node
        
        Args:
            node_id: Node identifier
            
        Returns:
            List of matching blocks
        """
        return [
            block for block in self.chain
            if block.data.get('node_id') == node_id
        ]
    
    def query(
        self,
        block_type: Optional[str] = None,
        node_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Block]:
        """
        Query blockchain with filters
        
        Args:
            block_type: Filter by block type
            node_id: Filter by node ID
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            
        Returns:
            List of matching blocks
        """
        results = self.chain[1:]  # Exclude genesis block
        
        if block_type:
            results = [b for b in results if b.data.get('type') == block_type]
        
        if node_id:
            results = [b for b in results if b.data.get('node_id') == node_id]
        
        if start_time:
            results = [b for b in results if b.timestamp >= start_time]
        
        if end_time:
            results = [b for b in results if b.timestamp <= end_time]
        
        return results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get blockchain summary statistics"""
        block_types = {}
        for block in self.chain[1:]:
            btype = block.data.get('type', 'unknown')
            block_types[btype] = block_types.get(btype, 0) + 1
        
        return {
            "total_blocks": len(self.chain),
            "is_valid": self.is_chain_valid(),
            "genesis_hash": self.chain[0].hash,
            "latest_hash": self.chain[-1].hash,
            "block_types": block_types,
            "first_timestamp": datetime.fromtimestamp(self.chain[0].timestamp).isoformat(),
            "last_timestamp": datetime.fromtimestamp(self.chain[-1].timestamp).isoformat()
        }


class SmartContract:
    """Simulated smart contract for participation and trust rules"""
    
    def __init__(self, blockchain: Blockchain):
        """
        Initialize smart contract
        
        Args:
            blockchain: Blockchain instance
        """
        self.blockchain = blockchain
        self.rules = {}
        self.registered_nodes = {}
        
    def register_node(
        self,
        node_id: str,
        node_info: Dict[str, Any]
    ) -> bool:
        """
        Register a node in the system
        
        Args:
            node_id: Node identifier
            node_info: Node information (name, address, etc.)
            
        Returns:
            True if registration successful
        """
        if node_id in self.registered_nodes:
            logger.warning(f"Node {node_id} already registered")
            return False
        
        self.registered_nodes[node_id] = {
            **node_info,
            "registered_at": time.time(),
            "trust_score": 1.0,
            "participation_count": 0,
            "quarantined": False
        }
        
        # Record on blockchain
        self.blockchain.add_block({
            "type": "node_registration",
            "node_id": node_id,
            "node_info": node_info,
            "timestamp": time.time()
        })
        
        logger.info(f"Registered node: {node_id}")
        return True
    
    def can_participate(self, node_id: str, round_number: int) -> bool:
        """
        Check if node can participate in FL round
        
        Args:
            node_id: Node identifier
            round_number: FL round number
            
        Returns:
            True if node can participate
        """
        if node_id not in self.registered_nodes:
            logger.warning(f"Node {node_id} not registered")
            return False
        
        node_info = self.registered_nodes[node_id]
        
        # Rule 1: Node must not be quarantined
        if node_info['quarantined']:
            logger.warning(f"Node {node_id} is quarantined")
            return False
        
        # Rule 2: Trust score must be above threshold
        min_trust_score = self.rules.get('min_trust_score', 0.5)
        if node_info['trust_score'] < min_trust_score:
            logger.warning(
                f"Node {node_id} trust score {node_info['trust_score']:.3f} "
                f"below threshold {min_trust_score}"
            )
            return False
        
        return True
    
    def record_participation(
        self,
        node_id: str,
        round_number: int,
        model_update_hash: str,
        metrics: Optional[Dict[str, float]] = None
    ):
        """
        Record node participation in FL round
        
        Args:
            node_id: Node identifier
            round_number: FL round number
            model_update_hash: Hash of model update
            metrics: Optional performance metrics
        """
        if node_id in self.registered_nodes:
            self.registered_nodes[node_id]['participation_count'] += 1
        
        # Record on blockchain
        self.blockchain.add_block({
            "type": "fl_round",
            "node_id": node_id,
            "round_number": round_number,
            "model_update_hash": model_update_hash,
            "metrics": metrics or {},
            "timestamp": time.time()
        })
        
        logger.info(f"Recorded participation: Node {node_id}, Round {round_number}")
    
    def update_trust_score(
        self,
        node_id: str,
        new_trust_score: float,
        reason: str
    ):
        """
        Update node trust score
        
        Args:
            node_id: Node identifier
            new_trust_score: New trust score (0.0 to 1.0)
            reason: Reason for update
        """
        if node_id not in self.registered_nodes:
            logger.warning(f"Cannot update trust for unregistered node: {node_id}")
            return
        
        old_score = self.registered_nodes[node_id]['trust_score']
        self.registered_nodes[node_id]['trust_score'] = max(0.0, min(1.0, new_trust_score))
        
        # Record on blockchain
        self.blockchain.add_block({
            "type": "trust_update",
            "node_id": node_id,
            "old_trust_score": old_score,
            "new_trust_score": new_trust_score,
            "reason": reason,
            "timestamp": time.time()
        })
        
        logger.info(
            f"Updated trust score for {node_id}: "
            f"{old_score:.3f} -> {new_trust_score:.3f} ({reason})"
        )
    
    def quarantine_node(
        self,
        node_id: str,
        reason: str
    ):
        """
        Quarantine a malicious or suspicious node
        
        Args:
            node_id: Node identifier
            reason: Reason for quarantine
        """
        if node_id not in self.registered_nodes:
            logger.warning(f"Cannot quarantine unregistered node: {node_id}")
            return
        
        self.registered_nodes[node_id]['quarantined'] = True
        self.registered_nodes[node_id]['trust_score'] = 0.0
        
        # Record on blockchain
        self.blockchain.add_block({
            "type": "quarantine",
            "node_id": node_id,
            "reason": reason,
            "timestamp": time.time()
        })
        
        logger.warning(f"QUARANTINED node {node_id}: {reason}")
    
    def release_quarantine(
        self,
        node_id: str,
        reason: str
    ):
        """
        Release node from quarantine
        
        Args:
            node_id: Node identifier
            reason: Reason for release
        """
        if node_id not in self.registered_nodes:
            return
        
        self.registered_nodes[node_id]['quarantined'] = False
        self.registered_nodes[node_id]['trust_score'] = 0.6  # Start with reduced trust
        
        # Record on blockchain
        self.blockchain.add_block({
            "type": "quarantine_release",
            "node_id": node_id,
            "reason": reason,
            "timestamp": time.time()
        })
        
        logger.info(f"Released node {node_id} from quarantine: {reason}")
    
    def log_security_event(
        self,
        event_type: str,
        node_id: Optional[str],
        details: Dict[str, Any]
    ):
        """
        Log a security event
        
        Args:
            event_type: Type of security event
            node_id: Related node ID (if applicable)
            details: Event details
        """
        self.blockchain.add_block({
            "type": "security_event",
            "event_type": event_type,
            "node_id": node_id,
            "details": details,
            "timestamp": time.time()
        })
        
        logger.info(f"Logged security event: {event_type} (Node: {node_id})")
    
    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a node"""
        return self.registered_nodes.get(node_id)
    
    def get_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        """Get all registered nodes"""
        return self.registered_nodes.copy()


class AuditLogger:
    """High-level audit logger using blockchain"""
    
    def __init__(self, blockchain: Blockchain, smart_contract: SmartContract):
        """
        Initialize audit logger
        
        Args:
            blockchain: Blockchain instance
            smart_contract: SmartContract instance
        """
        self.blockchain = blockchain
        self.smart_contract = smart_contract
    
    def log_fl_round_start(self, round_number: int, participating_nodes: List[str]):
        """Log start of FL round"""
        self.blockchain.add_block({
            "type": "fl_round_start",
            "round_number": round_number,
            "participating_nodes": participating_nodes,
            "num_participants": len(participating_nodes),
            "timestamp": time.time()
        })
    
    def log_fl_round_complete(
        self,
        round_number: int,
        global_model_hash: str,
        metrics: Dict[str, float]
    ):
        """Log completion of FL round"""
        self.blockchain.add_block({
            "type": "fl_round_complete",
            "round_number": round_number,
            "global_model_hash": global_model_hash,
            "metrics": metrics,
            "timestamp": time.time()
        })
    
    def log_anomaly_detected(
        self,
        node_id: str,
        anomaly_type: str,
        severity: str,
        details: Dict[str, Any]
    ):
        """Log anomaly detection"""
        self.smart_contract.log_security_event(
            event_type="anomaly_detected",
            node_id=node_id,
            details={
                "anomaly_type": anomaly_type,
                "severity": severity,
                **details
            }
        )
    
    def log_attack_detected(
        self,
        attack_type: str,
        source_info: Dict[str, Any],
        mitigation_action: str
    ):
        """Log DDoS attack detection"""
        self.blockchain.add_block({
            "type": "attack_detected",
            "attack_type": attack_type,
            "source_info": source_info,
            "mitigation_action": mitigation_action,
            "timestamp": time.time()
        })
    
    def generate_audit_report(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive audit report
        
        Args:
            start_time: Report start time
            end_time: Report end time
            
        Returns:
            Audit report dictionary
        """
        blocks = self.blockchain.query(start_time=start_time, end_time=end_time)
        
        report = {
            "period": {
                "start": datetime.fromtimestamp(start_time).isoformat() if start_time else "genesis",
                "end": datetime.fromtimestamp(end_time).isoformat() if end_time else "now"
            },
            "blockchain_valid": self.blockchain.is_chain_valid(),
            "total_events": len(blocks),
            "events_by_type": {},
            "fl_rounds": [],
            "security_events": [],
            "trust_updates": [],
            "quarantines": []
        }
        
        for block in blocks:
            btype = block.data.get('type', 'unknown')
            report['events_by_type'][btype] = report['events_by_type'].get(btype, 0) + 1
            
            if btype == "fl_round_complete":
                report['fl_rounds'].append(block.data)
            elif btype == "security_event":
                report['security_events'].append(block.data)
            elif btype == "trust_update":
                report['trust_updates'].append(block.data)
            elif btype == "quarantine":
                report['quarantines'].append(block.data)
        
        return report
