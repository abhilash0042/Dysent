"""
Real-time prediction with Explainable AI
Uses trained model to classify traffic and explain decisions
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import logging
from tensorflow import keras

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import FeatureExtractor
from ddosdfl.projects.shared_libs.explainable_ai import create_explainer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("RealTimeDetection")

# Real dataset path
REAL_DATA_PATH = Path("C:/Users/HP/Desktop/Major Project/Main File-Code/data/CIC-DDoS2019 Dataset/cicddos2019_dataset.csv")

# Trained model path (using best model)
MODEL_PATH = Path("c:/Users/HP/Desktop/Major Project/Main File-Code/ddosdfl/models/best_model.keras")

class RealTimeExplainableDetector:
    """Real-time DDoS detection with explanations"""
    
    def __init__(self, model_path: Path):
        """Initialize detector with trained model"""
        logger.info("Initializing Real-Time Explainable Detector...")
        
        # Load trained model
        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}, using fallback")
            # Use a simple model as fallback
            from ddosdfl.projects.shared_libs import CNNBiLSTMModel
            model_wrapper = CNNBiLSTMModel(input_shape=(10, 4), num_classes=2)
            self.model = model_wrapper.get_model()
        else:
            logger.info(f"Loading trained model from {model_path}")
            self.model = keras.models.load_model(model_path)
        
        # Initialize feature extractor
        self.feature_extractor = FeatureExtractor()
        
        # Feature names for CICDDoS2019
        self.feature_names = [
            'flow_duration', 'total_fwd_packets', 'total_bwd_packets',
            'packet_length_mean', 'packet_length_std', 'flow_bytes_per_sec',
            'flow_packets_per_sec', 'iat_mean', 'iat_std', 'fwd_iat_mean',
            'syn_flag_count', 'ack_flag_count', 'psh_flag_count', 'urg_flag_count'
        ][:4]  # Match model input
        
        # Initialize explainer
        self.explainer = create_explainer(self.model, self.feature_names)
        
        logger.info("✅ Detector initialized successfully")
    
    def predict_and_explain(self, traffic_sample: np.ndarray) -> dict:
        """
        Make prediction and generate explanation
        
        Args:
            traffic_sample: Preprocessed traffic features (10, 4)
            
        Returns:
            Dictionary with prediction and explanation
        """
        # Ensure correct shape
        if len(traffic_sample.shape) == 2:
            traffic_sample = np.expand_dims(traffic_sample, axis=0)
        
        # Get explanation (includes prediction)
        explanation = self.explainer.explain_prediction(traffic_sample)
        
        return explanation
    
    def monitor_real_traffic(self, data_path: Path, n_samples: int = 10):
        """
        Monitor real traffic from dataset and provide explanations
        
        Args:
            data_path: Path to traffic data CSV
            n_samples: Number of samples to analyze
        """
        logger.info(f"\n{'='*70}")
        logger.info("REAL-TIME TRAFFIC MONITORING WITH EXPLANATIONS")
        logger.info(f"{'='*70}\n")
        
        if not data_path.exists():
            logger.error(f"Data file not found: {data_path}")
            return
        
        # Load sample data
        logger.info(f"Loading {n_samples} samples from {data_path.name}...")
        df = pd.read_csv(data_path, nrows=n_samples*10, encoding='utf-8', low_memory=False)
        
        # Preprocess
        logger.info("Preprocessing traffic data...")
        X, y = self.feature_extractor.preprocess(df, fit=True)
        
        # Reshape for model
        if X.shape[1] < 40:
            X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
        else:
            X = X[:, :40]
        X = X.reshape(-1, 10, 4)
        
        # Randomly sample
        indices = np.random.choice(len(X), min(n_samples, len(X)), replace=False)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"ANALYZING {len(indices)} TRAFFIC SAMPLES")
        logger.info(f"{'='*70}\n")
        
        attack_count = 0
        benign_count = 0
        
        for i, idx in enumerate(indices, 1):
            sample = X[idx]
            true_label = int(y[idx])
            
            # Get prediction and explanation
            result = self.predict_and_explain(sample)
            
            # Display results
            logger.info(f"\n--- Sample {i}/{len(indices)} ---")
            logger.info(f"[Prediction]: {result['prediction_label']}")
            logger.info(f"[Confidence]: {result['confidence']*100:.1f}%")
            logger.info(f"[True Label]: {'Attack' if true_label == 1 else 'Benign'}")
            logger.info(f"[Explanation]: {result['explanation_text']}")
            
            if result['top_features']:
                logger.info("[Top Features]:")
                for j, (feature, contrib) in enumerate(result['top_features'].items(), 1):
                    logger.info(f"  {j}. {feature}: {contrib*100:.1f}%")
            
            if result['prediction'] == 1:
                attack_count += 1
            else:
                benign_count += 1
        
        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("DETECTION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total Samples Analyzed: {len(indices)}")
        logger.info(f"Attacks Detected: {attack_count} ({attack_count/len(indices)*100:.1f}%)")
        logger.info(f"Benign Traffic: {benign_count} ({benign_count/len(indices)*100:.1f}%)")
        logger.info(f"{'='*70}\n")

def main():
    """Run real-time explainable detection"""
    
    # Initialize detector
    detector = RealTimeExplainableDetector(MODEL_PATH)
    
    # Monitor real traffic
    detector.monitor_real_traffic(REAL_DATA_PATH, n_samples=5)
    
    logger.info("✅ Real-time detection complete!")

if __name__ == "__main__":
    main()
