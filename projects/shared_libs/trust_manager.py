"""
Trust Manager for Zero-Trust Security

Implements zero-trust principles for federated learning:
- Continuous authentication and authorization
- Trust scoring for nodes
- Anomaly detection in model updates
- Byzantine attack detection
"""

import numpy as np
import hashlib
import secrets
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
from collections import deque

logger = logging.getLogger(__name__)


class NodeCredentials:
    """Node authentication credentials"""
    
    def __init__(self, node_id: str):
        """
        Initialize node credentials
        
        Args:
            node_id: Node identifier
        """
        self.node_id = node_id
        self.api_key = self.generate_api_key()
        self.certificate = self.generate_certificate()
        self.created_at = datetime.now()
        self.last_auth = None
        
    def generate_api_key(self) -> str:
        """Generate secure API key"""
        return secrets.token_urlsafe(32)
    
    def generate_certificate(self) -> str:
        """Generate simulated certificate"""
        cert_data = f"{self.node_id}:{datetime.now().isoformat()}"
        return hashlib.sha256(cert_data.encode()).hexdigest()
    
    def verify_api_key(self, provided_key: str) -> bool:
        """Verify API key"""
        return secrets.compare_digest(self.api_key, provided_key)
    
    def update_last_auth(self):
        """Update last authentication timestamp"""
        self.last_auth = datetime.now()


class TrustScore:
    """Trust score calculation and management"""
    
    def __init__(self, initial_score: float = 1.0):
        """
        Initialize trust score
        
        Args:
            initial_score: Initial trust score (0.0 to 1.0)
        """
        self.score = max(0.0, min(1.0, initial_score))
        self.history = deque(maxlen=100)
        self.history.append((datetime.now(), self.score, "initialization"))
        
    def update(
        self,
        delta: float,
        reason: str,
        min_score: float = 0.0,
        max_score: float = 1.0
    ):
        """
        Update trust score
        
        Args:
            delta: Change in score (can be negative)
            reason: Reason for update
            min_score: Minimum allowed score
            max_score: Maximum allowed score
        """
        old_score = self.score
        self.score = max(min_score, min(max_score, self.score + delta))
        
        self.history.append((datetime.now(), self.score, reason))
        
        logger.info(
            f"Trust score updated: {old_score:.3f} -> {self.score:.3f} "
            f"(Δ={delta:+.3f}, reason: {reason})"
        )
    
    def get_score(self) -> float:
        """Get current trust score"""
        return self.score
    
    def get_history(self) -> List[Tuple[datetime, float, str]]:
        """Get trust score history"""
        return list(self.history)


class AnomalyDetector:
    """Detect anomalies in model updates"""
    
    def __init__(
        self,
        weight_change_threshold: float = 3.0,  # Standard deviations
        gradient_norm_threshold: float = 10.0
    ):
        """
        Initialize anomaly detector
        
        Args:
            weight_change_threshold: Threshold for weight change detection (std devs)
            gradient_norm_threshold: Threshold for gradient norm
        """
        self.weight_change_threshold = weight_change_threshold
        self.gradient_norm_threshold = gradient_norm_threshold
        self.historical_updates = deque(maxlen=50)
        
    def analyze_model_update(
        self,
        model_weights: List[np.ndarray],
        node_id: str
    ) -> Dict[str, Any]:
        """
        Analyze model update for anomalies
        
        Args:
            model_weights: Model weight arrays
            node_id: Node identifier
            
        Returns:
            Analysis results with anomaly indicators
        """
        logger.info(f"Analyzing model update from {node_id}...")
        
        # Calculate statistics
        stats = self._calculate_weight_statistics(model_weights)
        
        # Store in history
        self.historical_updates.append({
            "node_id": node_id,
            "timestamp": datetime.now(),
            "stats": stats
        })
        
        # Detect anomalies
        anomalies = []
        anomaly_score = 0.0
        
        # Check 1: Extreme weight values
        if stats['max_abs_weight'] > 100:
            anomalies.append("extreme_weight_values")
            anomaly_score += 0.3
            logger.warning(f"Node {node_id}: Extreme weight values detected")
        
        # Check 2: NaN or Inf values
        if stats['has_nan'] or stats['has_inf']:
            anomalies.append("invalid_values")
            anomaly_score += 0.5
            logger.warning(f"Node {node_id}: Invalid values (NaN/Inf) detected")
        
        # Check 3: Gradient norm check
        if stats['gradient_norm'] > self.gradient_norm_threshold:
            anomalies.append("high_gradient_norm")
            anomaly_score += 0.2
            logger.warning(
                f"Node {node_id}: High gradient norm "
                f"({stats['gradient_norm']:.2f})"
            )
        
        # Check 4: Deviation from historical patterns
        if len(self.historical_updates) >= 5:
            is_outlier, deviation = self._detect_outlier(stats)
            if is_outlier:
                anomalies.append("statistical_outlier")
                anomaly_score += 0.3
                logger.warning(
                    f"Node {node_id}: Statistical outlier detected "
                    f"(deviation: {deviation:.2f} std)"
                )
        
        # Check 5: Sign flipping attack
        if self._detect_sign_flip(model_weights):
            anomalies.append("sign_flip_attack")
            anomaly_score += 0.8
            logger.error(f"Node {node_id}: Possible sign flip attack detected!")
        
        return {
            "node_id": node_id,
            "timestamp": datetime.now().isoformat(),
            "statistics": stats,
            "anomalies": anomalies,
            "anomaly_score": min(1.0, anomaly_score),
            "is_suspicious": anomaly_score > 0.5
        }
    
    def _calculate_weight_statistics(
        self,
        weights: List[np.ndarray]
    ) -> Dict[str, float]:
        """Calculate statistics for model weights"""
        all_weights = np.concatenate([w.flatten() for w in weights])
        
        return {
            "mean": float(np.mean(all_weights)),
            "std": float(np.std(all_weights)),
            "min": float(np.min(all_weights)),
            "max": float(np.max(all_weights)),
            "max_abs_weight": float(np.max(np.abs(all_weights))),
            "gradient_norm": float(np.linalg.norm(all_weights)),
            "has_nan": bool(np.isnan(all_weights).any()),
            "has_inf": bool(np.isinf(all_weights).any()),
            "num_parameters": len(all_weights)
        }
    
    def _detect_outlier(
        self,
        current_stats: Dict[str, float]
    ) -> Tuple[bool, float]:
        """Detect if current update is a statistical outlier"""
        if len(self.historical_updates) < 5:
            return False, 0.0
        
        # Compare gradient norms
        historical_norms = [
            h['stats']['gradient_norm'] 
            for h in self.historical_updates
        ]
        
        mean_norm = np.mean(historical_norms)
        std_norm = np.std(historical_norms)
        
        if std_norm == 0:
            return False, 0.0
        
        current_norm = current_stats['gradient_norm']
        deviation = abs(current_norm - mean_norm) / std_norm
        
        is_outlier = deviation > self.weight_change_threshold
        
        return is_outlier, deviation
    
    def _detect_sign_flip(self, weights: List[np.ndarray]) -> bool:
        """Detect sign flipping attack"""
        # Check if majority of weights are negative (suspicious)
        # Most trained networks have roughly balanced signs
        all_weights = np.concatenate([w.flatten() for w in weights])
        negative_ratio = np.sum(all_weights < 0) / len(all_weights)
        
        # If more than 80% or less than 20% are negative, it's suspicious
        return negative_ratio > 0.8 or negative_ratio < 0.2


class TrustManager:
    """Main trust management system implementing zero-trust principles"""
    
    def __init__(
        self,
        min_trust_threshold: float = 0.5,
        anomaly_detector: Optional[AnomalyDetector] = None
    ):
        """
        Initialize trust manager
        
        Args:
            min_trust_threshold: Minimum trust score to participate
            anomaly_detector: Custom anomaly detector (creates default if None)
        """
        self.min_trust_threshold = min_trust_threshold
        self.anomaly_detector = anomaly_detector or AnomalyDetector()
        
        self.registered_nodes: Dict[str, Dict[str, Any]] = {}
        self.credentials: Dict[str, NodeCredentials] = {}
        self.trust_scores: Dict[str, TrustScore] = {}
        self.quarantined_nodes: set = set()
        
        logger.info(f"Initialized TrustManager with threshold {min_trust_threshold}")
    
    def register_node(
        self,
        node_id: str,
        node_info: Dict[str, Any]
    ) -> NodeCredentials:
        """
        Register a new node
        
        Args:
            node_id: Node identifier
            node_info: Node information
            
        Returns:
            Node credentials
        """
        if node_id in self.registered_nodes:
            raise ValueError(f"Node {node_id} already registered")
        
        # Create credentials
        credentials = NodeCredentials(node_id)
        self.credentials[node_id] = credentials
        
        # Initialize trust score
        self.trust_scores[node_id] = TrustScore(initial_score=1.0)
        
        # Store node info
        self.registered_nodes[node_id] = {
            **node_info,
            "registered_at": datetime.now(),
            "participation_count": 0,
            "successful_updates": 0,
            "failed_updates": 0
        }
        
        logger.info(f"Registered node: {node_id}")
        
        return credentials
    
    def authenticate_node(
        self,
        node_id: str,
        api_key: str
    ) -> bool:
        """
        Authenticate a node
        
        Args:
            node_id: Node identifier
            api_key: Provided API key
            
        Returns:
            True if authentication successful
        """
        if node_id not in self.credentials:
            logger.warning(f"Authentication failed: Unknown node {node_id}")
            return False
        
        credentials = self.credentials[node_id]
        
        if not credentials.verify_api_key(api_key):
            logger.warning(f"Authentication failed: Invalid API key for {node_id}")
            return False
        
        credentials.update_last_auth()
        logger.info(f"Node {node_id} authenticated successfully")
        
        return True
    
    def can_participate(
        self,
        node_id: str,
        round_number: int
    ) -> Tuple[bool, str]:
        """
        Check if node can participate in FL round (zero-trust check)
        
        Args:
            node_id: Node identifier
            round_number: FL round number
            
        Returns:
            Tuple of (can_participate, reason)
        """
        # Check 1: Node must be registered
        if node_id not in self.registered_nodes:
            return False, "Node not registered"
        
        # Check 2: Node must not be quarantined
        if node_id in self.quarantined_nodes:
            return False, "Node is quarantined"
        
        # Check 3: Trust score must be above threshold
        trust_score = self.trust_scores[node_id].get_score()
        if trust_score < self.min_trust_threshold:
            return False, f"Trust score ({trust_score:.3f}) below threshold ({self.min_trust_threshold})"
        
        # Check 4: Recent authentication
        credentials = self.credentials[node_id]
        if credentials.last_auth is None:
            return False, "No recent authentication"
        
        time_since_auth = datetime.now() - credentials.last_auth
        if time_since_auth > timedelta(hours=1):
            return False, "Authentication expired"
        
        return True, "Authorized"
    
    def validate_model_update(
        self,
        node_id: str,
        model_weights: List[np.ndarray]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate model update from node
        
        Args:
            node_id: Node identifier
            model_weights: Model weight arrays
            
        Returns:
            Tuple of (is_valid, analysis_results)
        """
        logger.info(f"Validating model update from {node_id}...")
        
        # Analyze for anomalies
        analysis = self.anomaly_detector.analyze_model_update(
            model_weights, node_id
        )
        
        is_valid = not analysis['is_suspicious']
        
        if is_valid:
            # Update trust score positively
            self.trust_scores[node_id].update(
                delta=0.01,
                reason="Valid model update"
            )
            self.registered_nodes[node_id]['successful_updates'] += 1
        else:
            # Update trust score negatively
            penalty = -0.1 * analysis['anomaly_score']
            self.trust_scores[node_id].update(
                delta=penalty,
                reason=f"Suspicious update: {', '.join(analysis['anomalies'])}"
            )
            self.registered_nodes[node_id]['failed_updates'] += 1
            
            # Quarantine if trust score drops too low
            if self.trust_scores[node_id].get_score() < 0.3:
                self.quarantine_node(
                    node_id,
                    reason="Trust score dropped below 0.3 due to suspicious updates"
                )
        
        return is_valid, analysis
    
    def quarantine_node(self, node_id: str, reason: str):
        """
        Quarantine a node
        
        Args:
            node_id: Node identifier
            reason: Reason for quarantine
        """
        self.quarantined_nodes.add(node_id)
        self.trust_scores[node_id].update(
            delta=-1.0,  # Set to 0
            reason=f"QUARANTINED: {reason}"
        )
        
        logger.error(f"QUARANTINED NODE {node_id}: {reason}")
    
    def release_quarantine(self, node_id: str, reason: str):
        """
        Release node from quarantine
        
        Args:
            node_id: Node identifier
            reason: Reason for release
        """
        if node_id in self.quarantined_nodes:
            self.quarantined_nodes.remove(node_id)
            
            # Restore trust score to 0.6 (reduced trust)
            current_score = self.trust_scores[node_id].get_score()
            self.trust_scores[node_id].update(
                delta=0.6 - current_score,
                reason=f"Released from quarantine: {reason}"
            )
            
            logger.info(f"Released {node_id} from quarantine: {reason}")
    
    def get_trust_score(self, node_id: str) -> float:
        """Get trust score for a node"""
        if node_id not in self.trust_scores:
            return 0.0
        return self.trust_scores[node_id].get_score()
    
    def get_node_status(self, node_id: str) -> Dict[str, Any]:
        """Get comprehensive status of a node"""
        if node_id not in self.registered_nodes:
            return {"error": "Node not found"}
        
        return {
            "node_id": node_id,
            "info": self.registered_nodes[node_id],
            "trust_score": self.get_trust_score(node_id),
            "is_quarantined": node_id in self.quarantined_nodes,
            "last_auth": self.credentials[node_id].last_auth.isoformat() 
                        if self.credentials[node_id].last_auth else None,
            "trust_history": [
                (ts.isoformat(), score, reason)
                for ts, score, reason in self.trust_scores[node_id].get_history()
            ]
        }
    
    def get_all_nodes_status(self) -> List[Dict[str, Any]]:
        """Get status of all nodes"""
        return [
            self.get_node_status(node_id)
            for node_id in self.registered_nodes.keys()
        ]
    
    def get_trusted_nodes(self) -> List[str]:
        """Get list of trusted nodes (above threshold, not quarantined)"""
        trusted = []
        for node_id in self.registered_nodes.keys():
            if (node_id not in self.quarantined_nodes and
                self.get_trust_score(node_id) >= self.min_trust_threshold):
                trusted.append(node_id)
        return trusted
    
    def summary(self):
        """Print trust management summary"""
        logger.info("\n" + "="*70)
        logger.info("TRUST MANAGEMENT SUMMARY")
        logger.info("="*70)
        logger.info(f"Total nodes: {len(self.registered_nodes)}")
        logger.info(f"Trusted nodes: {len(self.get_trusted_nodes())}")
        logger.info(f"Quarantined nodes: {len(self.quarantined_nodes)}")
        logger.info("\nNode Trust Scores:")
        for node_id in sorted(self.registered_nodes.keys()):
            trust = self.get_trust_score(node_id)
            status = "✓" if trust >= self.min_trust_threshold else "✗"
            quarantine = " [QUARANTINED]" if node_id in self.quarantined_nodes else ""
            logger.info(f"  {status} {node_id}: {trust:.3f}{quarantine}")
        logger.info("="*70)
