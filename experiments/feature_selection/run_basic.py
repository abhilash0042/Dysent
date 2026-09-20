"""
Feature Selection Demo and Comparison Script

Demonstrates different feature selection methods on your DDoS dataset
and compares their effectiveness.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))


import sys
import numpy as np
from pathlib import Path
import logging
import pickle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs.feature_selection import (
    FeatureSelector,
    compare_selection_methods
)

def main():
    """Run feature selection comparison"""
    logger.info("\n" + "🔍"*35)
    logger.info("Feature Selection Analysis - DDoS Detection")
    logger.info("🔍"*35 + "\n")
    
    # Load processed data
    processed_file = Path("data/processed/cicddos2019_full_processed.npz")
    
    if not processed_file.exists():
        logger.error(f"Processed data not found: {processed_file}")
        logger.info("Please run: python load_dataset.py first")
        return 1
    
    logger.info(f"Loading data from: {processed_file}")
    data = np.load(processed_file)
    X, y = data['X'], data['y']
    
    logger.info(f"Dataset: {X.shape[0]:,} samples, {X.shape[1]} features")
    logger.info(f"Classes: {len(np.unique(y))}")
    
    # Load feature names
    extractor_file = Path("data/processed/cicddos2019_full_feature_extractor.pkl")
    if extractor_file.exists():
        with open(extractor_file, 'rb') as f:
            extractor_data = pickle.load(f)
            feature_names = extractor_data.get('feature_names', None)
            logger.info(f"Loaded {len(feature_names)} feature names")
    else:
        feature_names = None
        logger.warning("Feature names not found, using indices")
    
    # Sample for faster computation
    if len(X) > 50000:
        logger.info(f"Sampling 50,000 records for faster analysis...")
        sample_idx = np.random.choice(len(X), 50000, replace=False)
        X_sample, y_sample = X[sample_idx], y[sample_idx]
    else:
        X_sample, y_sample = X, y
    
    # Compare methods
    print("\n" + "="*70)
    print("Select number of features to keep:")
    print("Recommendation: 40-50 for CNN-BiLSTM (from 79 original features)")
    top_k = int(input("Enter number of features (default 40): ").strip() or "40")
    
    results = compare_selection_methods(
        X_sample,
        y_sample,
        feature_names=feature_names,
        top_k=top_k
    )
    
    # Save results
    logger.info("\n" + "="*70)
    logger.info("Saving Feature Selection Results")
    logger.info("="*70)
    
    output_dir = Path("data/processed")
    results_file = output_dir / f"feature_selection_top{top_k}.pkl"
    
    with open(results_file, 'wb') as f:
        pickle.dump(results, f)
    
    logger.info(f"Saved to: {results_file}")
    
    # Apply recommended method (ensemble)
    logger.info("\n" + "="*70)
    logger.info("Applying ENSEMBLE Feature Selection")
    logger.info("="*70)
    
    ensemble_indices = results['ensemble']
    X_selected = X[:, ensemble_indices]
    
    # Save selected features
    selected_file = output_dir / f"cicddos2019_full_selected_{top_k}features.npz"
    np.savez_compressed(
        selected_file,
        X=X_selected,
        y=y,
        selected_indices=ensemble_indices,
        feature_names=[feature_names[i] if feature_names else f"F{i}" 
                      for i in ensemble_indices]
    )
    
    logger.info(f"Saved selected features to: {selected_file}")
    
    # Print recommendation
    logger.info("\n" + "✅"*35)
    logger.info("FEATURE SELECTION COMPLETE!")
    logger.info("✅"*35)
    
    logger.info(f"\nOriginal features: {X.shape[1]}")
    logger.info(f"Selected features: {len(ensemble_indices)}")
    logger.info(f"Reduction: {(1 - len(ensemble_indices)/X.shape[1])*100:.1f}%")
    
    logger.info("\nRecommendation:")
    logger.info(f"  Use ENSEMBLE method ({top_k} features)")
    logger.info(f"  Combines: Mutual Info + ANOVA + Random Forest")
    logger.info(f"  Most robust across different selection criteria")
    
    logger.info("\nNext steps:")
    logger.info("1. Rerun load_dataset.py with selected features")
    logger.info("2. Train CNN-BiLSTM with reduced feature set")
    logger.info("3. Compare accuracy: All features vs Selected features")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
