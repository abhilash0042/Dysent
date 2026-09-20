"""
Continuous real-time monitoring with dashboard integration
Monitors traffic and sends explanations to dashboard
"""

import sys
from pathlib import Path
import numpy as np
import time
import requests
import logging
from threading import Thread

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.tests.test_realtime_detection import RealTimeExplainableDetector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("ContinuousMonitor")

# Paths
MODEL_PATH = Path("c:/Users/HP/Desktop/Major Project/Main File-Code/ddosdfl/models/best_model.keras")
DATA_PATH = Path("C:/Users/HP/Desktop/Major Project/Main File-Code/data/CIC-DDoS2019 Dataset/cicddos2019_dataset.csv")
DASHBOARD_URL = "http://localhost:5000/api/attack_detected"

class ContinuousMonitor:
    """Continuous monitoring with live dashboard updates"""
    
    def __init__(self):
        self.detector = RealTimeExplainableDetector(MODEL_PATH)
        self.is_monitoring = False
        
    def monitor_continuously(self, interval=5, batch_size=10):
        """
        Monitor traffic continuously and send to dashboard
        
        Args:
            interval: Seconds between batches
            batch_size: Number of samples per interval
        """
        logger.info("Starting continuous monitoring...")
        logger.info(f"Dashboard URL: {DASHBOARD_URL}")
        logger.info(f"Monitoring interval: {interval}s, batch size: {batch_size}")
        
        self.is_monitoring = True
        
        # Load data once
        import pandas as pd
        logger.info("Loading dataset...")
        df = pd.read_csv(DATA_PATH, nrows=10000, encoding='utf-8', low_memory=False)
        
        # Preprocess
        X, y = self.detector.feature_extractor.preprocess(df, fit=True)
        if X.shape[1] < 40:
            X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
        else:
            X = X[:, :40]
        X = X.reshape(-1, 10, 4)
        
        logger.info(f"Dataset loaded: {len(X)} samples")
        logger.info("\n" + "="*70)
        logger.info("LIVE MONITORING ACTIVE - Sending to Dashboard")
        logger.info("="*70 + "\n")
        
        sample_idx = 0
        
        while self.is_monitoring:
            # Get batch
            batch_indices = []
            for _ in range(batch_size):
                if sample_idx >= len(X):
                    sample_idx = 0  # Loop back
                batch_indices.append(sample_idx)
                sample_idx += 1
            
            # Process batch
            for idx in batch_indices:
                sample = X[idx]
                true_label = int(y[idx])
                
                # Get prediction with explanation
                result = self.detector.predict_and_explain(sample)
                
                # Log to console
                logger.info(f"[{result['prediction_label']}] Confidence: {result['confidence']*100:.1f}% | True: {'Attack' if true_label ==1 else 'Benign'}")
                
                # Send to dashboard
                try:
                    response = requests.post(DASHBOARD_URL, json={
                        'prediction': result['prediction_label'],
                        'confidence': result['confidence'],
                        'explanation': result['explanation_text'],
                        'top_features': result['top_features']
                    }, timeout=1)
                    
                    if response.status_code == 200:
                        logger.info("  -> Sent to dashboard")
                except Exception as e:
                    logger.warning(f"  -> Dashboard not reachable: {e}")
            
            # Wait before next batch
            time.sleep(interval)
    
    def stop(self):
        """Stop monitoring"""
        self.is_monitoring = False
        logger.info("Monitoring stopped")

def main():
    """Run continuous monitoring"""
    monitor = ContinuousMonitor()
    
    try:
        monitor.monitor_continuously(interval=3, batch_size=5)
    except KeyboardInterrupt:
        logger.info("\nStopping monitoring...")
        monitor.stop()

if __name__ == "__main__":
    main()
