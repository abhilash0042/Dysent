"""
Check class distribution in the CICDDoS2019 dataset
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import FeatureExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClassDistribution")

# Dataset Path
DATASET_ROOT = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset")

def analyze_class_distribution():
    logger.info("="*70)
    logger.info("📊 ANALYZING CLASS DISTRIBUTION")
    logger.info("="*70)
    
    if not DATASET_ROOT.exists():
        logger.error(f"❌ Path not found: {DATASET_ROOT}")
        return
    
    # Find all CSVs
    csv_files = list(DATASET_ROOT.rglob("*.csv"))
    logger.info(f"Found {len(csv_files)} CSV files\n")
    
    if not csv_files:
        logger.error("No CSV files found!")
        return
    
    # Analyze each file
    total_benign = 0
    total_attack = 0
    
    SAMPLES_PER_FILE = 40000  # Same as training script
    
    for file in csv_files:
        try:
            logger.info(f"Analyzing {file.name}...")
            
            # Read sample
            df = pd.read_csv(file, nrows=SAMPLES_PER_FILE, encoding='utf-8', low_memory=False)
            
            # Find label column
            label_col = None
            for col in ['Label', 'label', ' Label']:
                if col in df.columns:
                    label_col = col
                    break
            
            if label_col is None:
                logger.warning(f"  ⚠️ No label column found in {file.name}")
                continue
            
            # Count classes
            value_counts = df[label_col].value_counts()
            
            # Determine benign vs attack
            # CICDDoS2019 uses "BENIGN" or "Benign" for benign traffic
            benign_count = 0
            attack_count = 0
            
            for label, count in value_counts.items():
                label_str = str(label).upper()
                if 'BENIGN' in label_str:
                    benign_count += count
                else:
                    attack_count += count
            
            total_benign += benign_count
            total_attack += attack_count
            
            logger.info(f"  Benign: {benign_count:,} | Attack: {attack_count:,}")
            if benign_count + attack_count > 0:
                attack_ratio = attack_count / (benign_count + attack_count) * 100
                logger.info(f"  Attack Ratio: {attack_ratio:.1f}%\n")
            
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to read {file.name}: {e}")
    
    # Overall statistics
    logger.info("="*70)
    logger.info("📊 OVERALL CLASS DISTRIBUTION")
    logger.info("="*70)
    logger.info(f"Total Benign:  {total_benign:,}")
    logger.info(f"Total Attack:  {total_attack:,}")
    logger.info(f"Total Samples: {total_benign + total_attack:,}")
    
    if total_benign + total_attack > 0:
        benign_pct = total_benign / (total_benign + total_attack) * 100
        attack_pct = total_attack / (total_benign + total_attack) * 100
        
        logger.info(f"\nBenign: {benign_pct:.2f}%")
        logger.info(f"Attack: {attack_pct:.2f}%")
        
        # Check for imbalance
        imbalance_ratio = max(total_benign, total_attack) / min(total_benign, total_attack) if min(total_benign, total_attack) > 0 else float('inf')
        logger.info(f"\nImbalance Ratio: {imbalance_ratio:.2f}:1")
        
        if imbalance_ratio > 3:
            logger.warning("\n⚠️ WARNING: Significant class imbalance detected!")
            logger.warning("High accuracy may be misleading.")
            logger.warning("Recommendation: Use balanced_accuracy, F1-score, or precision/recall metrics.")
        else:
            logger.info("\n✅ Dataset is reasonably balanced")
    
    logger.info("="*70)

if __name__ == "__main__":
    analyze_class_distribution()
