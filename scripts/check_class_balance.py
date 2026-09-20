"""
Quick class distribution check
"""

import pandas as pd
from pathlib import Path

# Dataset path
DATASET_PATH = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset\cicddos2019_dataset.csv")

print("\n" + "="*70)
print("📊 CLASS DISTRIBUTION ANALYSIS")
print("="*70)

# Read a large sample
print(f"\nReading dataset from: {DATASET_PATH.name}")
df = pd.read_csv(DATASET_PATH, nrows=100000, encoding='utf-8', low_memory=False)

print(f"Total samples read: {len(df):,}\n")

# Find label column
label_col = None
for col in ['Label', 'label', ' Label']:
    if col in df.columns:
        label_col = col
        break

if label_col:
    print(f"Label column: '{label_col}'\n")
    
    # Get value counts
    value_counts = df[label_col].value_counts()
    
    print("Class Distribution:")
    print("-" * 50)
    
    total = len(df)
    benign_count = 0
    attack_count = 0
    
    for label, count in value_counts.items():
        pct = (count / total) * 100
        print(f"  {label}: {count:,} ({pct:.2f}%)")
        
        # Categorize
        if 'BENIGN' in str(label).upper():
            benign_count += count
        else:
            attack_count += count
    
    print("\n" + "="*70)
    print("SUMMARY:")
    print("="*70)
    print(f"Benign Traffic:  {benign_count:,} ({benign_count/total*100:.2f}%)")
    print(f"Attack Traffic:  {attack_count:,} ({attack_count/total*100:.2f}%)")
    
    if benign_count > 0 and attack_count > 0:
        ratio = max(benign_count, attack_count) / min(benign_count, attack_count)
        print(f"\nImbalance Ratio: {ratio:.2f}:1")
        
        if ratio > 3:
            print("\n⚠️  WARNING: SIGNIFICANT IMBALANCE!")
            print("98.85% accuracy may be inflated.")
            print("\nRecommendations:")
            print("  1. Check Balanced Accuracy")
            print("  2. Review Precision/Recall per class")
            print("  3. Use F1-Score")
            print("  4. Check Confusion Matrix")
        else:
            print("\n✅ Dataset is reasonably balanced")
    
    print("="*70 + "\n")
else:
    print("❌ No label column found!")
