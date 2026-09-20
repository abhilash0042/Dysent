"""
Comprehensive Dataset Analysis & Normalized Sampling
Scans all 18 CICDDoS2019 files to determine exact class distribution.
Creates a balanced (normalized) training set.
"""

import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import gc

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("DatasetNormalizer")

DATASET_ROOT = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset")

def scan_and_analyze():
    """
    Step 1: Scan all files to get raw counts of Benign vs Attack
    """
    logger.info("="*70)
    logger.info("📊 FULL DATASET SCAN (Step 1 of 2)")
    logger.info("="*70)
    
    csv_files = list(DATASET_ROOT.rglob("*.csv"))
    logger.info(f"Found {len(csv_files)} files.")
    
    total_benign = 0
    total_attack = 0
    file_stats = {}
    
    for i, file in enumerate(csv_files):
        try:
            # Just read the label column to be fast
            # Note: The column name might vary (' Label', 'Label', etc.)
            # We read first row to check columns
            peek = pd.read_csv(file, nrows=1)
            label_col = [c for c in peek.columns if "Label" in c]
            if not label_col:
                continue
            label_col = label_col[0]
            
            # Read only label column
            df = pd.read_csv(file, usecols=[label_col], encoding='utf-8', low_memory=False)
            
            # Normalize labels (strip whitespace, uppercase)
            # Efficiently using vector operations
            labels = df[label_col].astype(str).str.strip().str.upper()
            
            # Simple Benign check (CICDDoS2019 uses 'BENIGN')
            benign_mask = labels == 'BENIGN'
            n_benign = benign_mask.sum()
            n_attack = len(df) - n_benign
            
            total_benign += n_benign
            total_attack += n_attack
            
            file_stats[file.name] = {
                'benign': n_benign,
                'attack': n_attack,
                'path': file
            }
            
            logger.info(f"[{i+1}/{len(csv_files)}] {file.name}: Benign={n_benign:,}, Attack={n_attack:,}")
            
            # Clear memory
            del df
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error reading {file.name}: {e}")

    logger.info("-" * 50)
    logger.info(f"TOTAL BENIGN: {total_benign:,}")
    logger.info(f"TOTAL ATTACK: {total_attack:,}")
    logger.info("-" * 50)
    
    return total_benign, total_attack, file_stats

def create_balanced_sample(file_stats, total_benign, target_samples=200000, benign_ratio=0.5):
    """
    Step 2: Create a balanced dataset with custom ratio
    benign_ratio: 0.5 for 50/50, 0.75 for 75/25 Benign/Attack
    """
    logger.info("\n" + "="*70)
    logger.info(f"⚖️ CREATING CUSTOM DATASET (Ratio: {benign_ratio*100:.0f}% Benign)")
    logger.info("="*70)
    
    # Calculate limits based on ratio
    # If benign_ratio = 0.75, then Benign = 3 * Attack
    # Limit is based on whichever class is the bottleneck relative to the ratio
    
    # Check max possible based on Benign count
    # total_benign is the cap for the benign part
    # If we want 75% benign, max total samples = total_benign / 0.75
    
    max_total_by_benign = total_benign / benign_ratio
    
    # We arbitrary limit target_samples to avoid huge datasets if user asks
    effective_total = min(target_samples, max_total_by_benign)
    
    target_benign_count = int(effective_total * benign_ratio)
    target_attack_count = int(effective_total * (1 - benign_ratio))
    
    # Safety Check: If we don't have enough Benign
    if target_benign_count > total_benign:
        logger.warning(f"Requested {target_benign_count} Benign, but only have {total_benign}. Adjusting...")
        target_benign_count = total_benign
        # Recalculate attack to maintain ratio? Or just take what we can?
        # Let's simple cap attack to maintain ratio roughly or just take the math
        target_attack_count = int(target_benign_count * (1 - benign_ratio) / benign_ratio)
    
    logger.info(f"Targeting Split: {target_benign_count:,} Benign / {target_attack_count:,} Attack")
    
    limit_benign = target_benign_count
    limit_attack = target_attack_count

    # Calculate sampling rates
    # We will iterate through files and greedily collect
    
    final_dfs = []
    collected_benign = 0
    collected_attack = 0

    for fname, stats in file_stats.items():
        if collected_benign >= limit_benign and collected_attack >= limit_attack:
            break
            
        file_path = stats['path']
        
        try:
            # Read full file (iteratively if needed, but for sampling we try chunks)
            # To be precise, we load the file filter rows.
            
            df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)
            
            # Identify columns
            cols = [c for c in df.columns if "Label" in c]
            if not cols:
                continue
            label_col = cols[0]
            
            # Normalize labels (strip whitespace, uppercase)
            df[label_col] = df[label_col].astype(str).str.strip().str.upper()
            
            # Split
            df_benign = df[df[label_col] == 'BENIGN']
            df_attack = df[df[label_col] != 'BENIGN']
            
            # Take Benign
            needed_benign = limit_benign - collected_benign
            if needed_benign > 0 and len(df_benign) > 0:
                take_b = min(needed_benign, len(df_benign))
                final_dfs.append(df_benign.sample(n=take_b, random_state=42))
                collected_benign += take_b
                
            # Take Attack
            needed_attack = limit_attack - collected_attack
            if needed_attack > 0 and len(df_attack) > 0:
                # Distribution Strategy:
                # We want diversity.
                # Max from this file: roughly (limit_attack / num_files * 2) to allow some variance
                # but ensure we fill up.
                max_from_this_file = max(limit_attack // 5, 1000) # Slightly more aggressive sampling
                
                take_a = min(needed_attack, len(df_attack), max_from_this_file)
                
                final_dfs.append(df_attack.sample(n=take_a, random_state=42))
                collected_attack += take_a
                
            logger.info(f"  Processed {fname}: Got {collected_benign:,} B / {collected_attack:,} A so far...")
            
            del df, df_benign, df_attack
            gc.collect()
            
        except Exception as e:
            logger.error(f"  Skipping {fname} due to error: {e}")

    # Combine
    logger.info("Concatenating final dataset...")
    full_df = pd.concat(final_dfs, ignore_index=True)
    
    # Verify Balance
    b_count = (full_df[label_col] == 'BENIGN').sum()
    a_count = len(full_df) - b_count
    
    logger.info("\n" + "-"*50)
    logger.info("✅ NORMALIZED DATASET READY")
    logger.info(f"Total Records: {len(full_df):,}")
    logger.info(f"Benign: {b_count:,} ({b_count/len(full_df)*100:.1f}%)")
    logger.info(f"Attack: {a_count:,} ({a_count/len(full_df)*100:.1f}%)")
    logger.info("-" * 50)
    
    # Save or Return?
    # For this flow, we will return df for training immediately
    return full_df

if __name__ == "__main__":
    benign, attack, stats = scan_and_analyze()
    
    # 1. Generate 50/50
    df_50 = create_balanced_sample(stats, benign, benign_ratio=0.5)
    save_path_50 = project_root / "ddosdfl" / "dataset_50_50.csv"
    df_50.to_csv(save_path_50, index=False)
    logger.info(f"✅ Saved 50/50 dataset to {save_path_50}")
    
    # 2. Generate 75/25 (Inverted Imbalance)
    df_75 = create_balanced_sample(stats, benign, benign_ratio=0.75)
    save_path_75 = project_root / "ddosdfl" / "dataset_75_25.csv"
    df_75.to_csv(save_path_75, index=False)
    logger.info(f"✅ Saved 75/25 dataset to {save_path_75}")
