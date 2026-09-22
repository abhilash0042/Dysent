"""Shared libraries for DDoS Detection System.

Heavy ML dependencies are optional at package-import time so SDN/PCMI/attack
utilities can be tested independently in lightweight environments.
"""
from .config_loader import ConfigLoader
from .data_processor import DatasetLoader, FeatureExtractor, DataPartitioner, split_data
from .trust_manager import TrustManager, NodeCredentials, TrustScore, AnomalyDetector
from .blockchain_interface import Blockchain, SmartContract, Block, AuditLogger
from .openrouter_client import OpenRouterClient, AgentDecisionEngine, DDoSAgentPrompts

try:
    from .cnn_bilstm_model import CNNBiLSTMModel, ModelTrainer, ModelEvaluator
except ImportError:
    CNNBiLSTMModel = ModelTrainer = ModelEvaluator = None

try:
    from .transformer_model import TransformerModel
except ImportError:
    TransformerModel = None

__all__ = [
    'ConfigLoader', 'DatasetLoader', 'FeatureExtractor', 'DataPartitioner', 'split_data',
    'CNNBiLSTMModel', 'TransformerModel', 'ModelTrainer', 'ModelEvaluator',
    'TrustManager', 'NodeCredentials', 'TrustScore', 'AnomalyDetector',
    'Blockchain', 'SmartContract', 'Block', 'AuditLogger',
    'OpenRouterClient', 'AgentDecisionEngine', 'DDoSAgentPrompts',
]
