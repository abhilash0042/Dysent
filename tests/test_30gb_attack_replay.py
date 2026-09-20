"""
30GB Attack Replay Simulation
Streams the massive CICDDoS2019 dataset to simulate high-volume attack traffic.
Demonstrates the model's ability to handle scale.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import time
import requests
import logging

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.tests.test_realtime_detection import RealTimeExplainableDetector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("AttackReplay")

# Config
DATASET_PATH = Path("C:/Users/HP/Desktop/Major Project/Main File-Code/data/CIC-DDoS2019 Dataset/cicddos2019_dataset.csv")
MODEL_PATH = Path("c:/Users/HP/Desktop/Major Project/Main File-Code/ddosdfl/models/best_model.keras")
DASHBOARD_URL_ATTACK = "http://localhost:5000/api/attack_detected"
DASHBOARD_URL_STATUS = "http://localhost:5000/api/update_metrics"  # Only if we implement this, otherwise we might piggyback

class AttackReplay:
    def __init__(self):
        self.detector = RealTimeExplainableDetector(MODEL_PATH)
        self.processed_count = 0
        self.start_time = time.time()
        
    def stream_dataset(self, chunk_size=1000):
        """Stream dataset in large chunks to simulate high volume"""
        
        logger.info(f"\n{'='*70}")
        logger.info("🚀 STARTING 30GB ATTACK REPLAY SIMULATION")
        logger.info(f"Source: {DATASET_PATH}")
        logger.info(f"Mode: High-Throughput Streaming")
        logger.info(f"{'='*70}\n")
        
        if not DATASET_PATH.exists():
            logger.error("Dataset not found! Please check path.")
            return

        # Estimate total lines (approx for 30GB)
        # 30GB ~ 30,000,000,000 bytes. Avg line ~200 bytes? -> 150M lines?
        
        # DEMO MODE: Read larger chunks and filter for attacks to ensure visual activity
        chunk_iterator = pd.read_csv(
            DATASET_PATH, 
            chunksize=chunk_size, 
            low_memory=False,
            encoding='utf-8'
        )
        
        logger.info("Initializing feature extractor...")
        
        # DEMO HACK: If we don't find attacks in first few chunks, skip ahead or inject simulated ones
        # Real dataset often has long periods of benign traffic
        
        for i, chunk in enumerate(chunk_iterator):
            batch_start = time.time()
            
            # Simple simulation of "Attack" detection if dataset is all benign in this chunk
            # This ensures the demo looks active even if we are hitting a benign-only patch
            # In production we would process strictly, but for demo we want to show CAPABILITY
            
            try:
                X, y = self.detector.feature_extractor.preprocess(chunk, fit=True)
                
                # Reshape
                if X.shape[1] < 40:
                    X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
                else:
                    X = X[:, :40]
                X = X.reshape(-1, 10, 4)
                
                # Predict
                predictions = self.detector.model.predict(X, verbose=0)
                pred_classes = np.argmax(predictions, axis=1)
                
                # DEMO ENHANCEMENT:
                # If we have 0 attacks in this chunk (boring), and it's a demo...
                # Let's verify if the label column actually has attacks (1)
                true_attacks = np.sum(y == 1) if y is not None else 0
                
                # If model missed them OR there were none, but we want to show alerting capability:
                # We can't fake it, but we can search for a chunk WITH attacks.
                # For now, let's just log what we found.
                
                attack_indices = np.where(pred_classes != 0)[0]
                
                # Stats
                self.processed_count += len(X)
                throughput = len(X) / (max(time.time() - batch_start, 0.001))
                
                # Highlight in log if attack found
                status_icon = "🔴" if len(attack_indices) > 0 else "🟢"
                logger.info(f"{status_icon} Chunk #{i+1}: {len(attack_indices)} Attacks / {len(X)} Samples | Speed: {throughput:.0f} samples/sec")
                
                # If attacks found, explain detailedly for a few of them
                if len(attack_indices) > 0:
                    idx = attack_indices[0]
                    explanation = self.detector.predict_and_explain(X[idx])
                    self._send_dashboard_alert(explanation, throughput)
                    
                # Skip benign chunks faster to find attacks?
                # if len(attack_indices) == 0: continue

            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                continue
                
            # Optional: artificial delay if too fast, or just let it rip
            # time.sleep(0.1) 

    def _send_dashboard_alert(self, explanation, throughput):
        try:
            # We can piggyback throughput in the 'explanation' or a separate field if dashboard supports it
            # Or just send the attack
            payload = {
                'prediction': explanation['prediction_label'],
                'confidence': explanation['confidence'],
                'explanation': f"{explanation['explanation_text']} [Throughput: {throughput:.0f} samples/s]",
                'top_features': explanation['top_features']
            }
            requests.post(DASHBOARD_URL_ATTACK, json=payload, timeout=0.1)
        except:
            pass

if __name__ == "__main__":
    replay = AttackReplay()
    try:
        replay.stream_dataset()
    except KeyboardInterrupt:
        logger.info("Replay stopped by user.")
