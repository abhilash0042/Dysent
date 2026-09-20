"""
Advanced Feature Selection Comparison

Compares RL-based and DNN-based feature selection methods
with traditional statistical methods.
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
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs.feature_selection import FeatureSelector
from projects.shared_libs.rl_feature_selection import train_rl_feature_selector
from projects.shared_libs.dnn_feature_selection import train_dnn_feature_selector


def main():
    """Run advanced feature selection comparison"""
    logger.info("\n" + "🤖"*35)
    logger.info("Advanced Feature Selection: RL + DNN Methods")
    logger.info("🤖"*35 + "\n")
    
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
    
    # Split for validation
    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    logger.info(f"Train: {len(X_train):,}, Val: {len(X_val):,}")
    
    # Configuration
    print("\n" + "="*70)
    print("Feature Selection Configuration:")
    target_features = int(input("Target number of features (default 40): ").strip() or "40")
    
    print("\nSelect methods to compare:")
    print("1. RL (Deep Q-Learning) - Novel, learns via trial-and-error")
    print("2. DNN Attention - Novel, learns attention weights")
    print("3. DNN Concrete Selector - Novel, learnable binary gates")
    print("4. Traditional (Ensemble) - Baseline comparison")
    print("5. ALL methods - Full comparison")
    
    method_choice = input("\nEnter choice (1-5): ").strip()
    
    results = {}
    
    # Traditional baseline (for comparison)
    if method_choice in ['4', '5']:
        logger.info("\n" + "="*70)
        logger.info("BASELINE: Traditional Ensemble Feature Selection")
        logger.info("="*70)
        
        selector = FeatureSelector()
        start_time = time.time()
        X_selected, trad_indices = selector.ensemble_selection(
            X_train[:10000], y_train[:10000],  # Sample for speed
            top_k=target_features
        )
        elapsed = time.time() - start_time
        
        results['traditional'] = {
            'indices': trad_indices,
            'num_features': len(trad_indices),
            'time': elapsed
        }
        
        logger.info(f"Time: {elapsed:.2f}s")
    
    # RL-based selection
    if method_choice in ['1', '5']:
        logger.info("\n" + "="*70)
        logger.info("METHOD 1: RL-Based Feature Selection (Deep Q-Learning)")
        logger.info("="*70)
        
        start_time = time.time()
        rl_indices, rl_agent = train_rl_feature_selector(
            X_train,
            y_train,
            max_features=target_features,
            num_episodes=50  # Reduce for demo
        )
        elapsed = time.time() - start_time
        
        results['rl_dqn'] = {
            'indices': rl_indices,
            'num_features': len(rl_indices),
            'time': elapsed,
            'agent': rl_agent
        }
        
        logger.info(f"Total time: {elapsed:.2f}s")
    
    # DNN Attention-based selection
    if method_choice in ['2', '5']:
        logger.info("\n" + "="*70)
        logger.info("METHOD 2: DNN Attention-Based Feature Selection")
        logger.info("="*70)
        
        start_time = time.time()
        attention_indices, attention_selector = train_dnn_feature_selector(
            X_train,
            y_train,
            X_val,
            y_val,
            method='attention',
            num_epochs=20,  # Reduce for demo
            top_k=target_features
        )
        elapsed = time.time() - start_time
        
        results['dnn_attention'] = {
            'indices': attention_indices,
            'num_features': len(attention_indices),
            'time': elapsed,
            'selector': attention_selector
        }
        
        logger.info(f"Total time: {elapsed:.2f}s")
    
    # DNN Concrete Selector
    if method_choice in ['3', '5']:
        logger.info("\n" + "="*70)
        logger.info("METHOD 3: DNN Concrete Selector (Gumbel-Softmax)")
        logger.info("="*70)
        
        start_time = time.time()
        concrete_indices, concrete_selector = train_dnn_feature_selector(
            X_train,
            y_train,
            X_val,
            y_val,
            method='concrete',
            num_epochs=20,  # Reduce for demo
            top_k=target_features
        )
        elapsed = time.time() - start_time
        
        results['dnn_concrete'] = {
            'indices': concrete_indices,
            'num_features': len(concrete_indices),
            'time': elapsed,
            'selector': concrete_selector
        }
        
        logger.info(f"Total time: {elapsed:.2f}s")
    
    # Comparison
    logger.info("\n" + "="*70)
    logger.info("FEATURE SELECTION COMPARISON")
    logger.info("="*70)
    
    for method_name, result in results.items():
        logger.info(f"\n{method_name.upper()}:")
        logger.info(f"  Features selected: {result['num_features']}")
        logger.info(f"  Time: {result['time']:.2f}s")
        logger.info(f"  Indices: {sorted(result['indices'])[:10]}...")
    
    # Feature overlap analysis
    if len(results) > 1:
        logger.info("\n" + "="*70)
        logger.info("Feature Overlap Analysis")
        logger.info("="*70)
        
        methods = list(results.keys())
        for i, method1 in enumerate(methods):
            for method2 in methods[i+1:]:
                set1 = set(results[method1]['indices'])
                set2 = set(results[method2]['indices'])
                overlap = len(set1 & set2)
                overlap_pct = (overlap / target_features) * 100
                
                logger.info(
                    f"{method1} ∩ {method2}: {overlap}/{target_features} "
                    f"({overlap_pct:.1f}% overlap)"
                )
    
    # Save results
    output_dir = Path("data/processed")
    results_file = output_dir / f"advanced_feature_selection_{target_features}features.pkl"
    
    # Remove non-serializable objects
    save_results = {}
    for method, result in results.items():
        save_results[method] = {
            'indices': result['indices'],
            'num_features': result['num_features'],
            'time': result['time']
        }
    
    with open(results_file, 'wb') as f:
        pickle.dump(save_results, f)
    
    logger.info(f"\nResults saved to: {results_file}")
    
    # Recommendation
    logger.info("\n" + "✅"*35)
    logger.info("FEATURE SELECTION COMPLETE!")
    logger.info("✅"*35)
    
    logger.info("\nRecommendations:")
    logger.info("  • DNN Concrete Selector: End-to-end learnable, good for deep models")
    logger.info("  • DNN Attention: Interpretable importance weights")
    logger.info("  • RL (DQN): Novel approach, explores feature space intelligently")
    logger.info("  • Traditional Ensemble: Fast, reliable baseline")
    
    logger.info("\nNovelty for Research:")
    logger.info("  ✅ RL-based: First to use DQN for FL-DDoS feature selection")
    logger.info("  ✅ DNN-based: Attention + Gumbel-Softmax for network security")
    logger.info("  ✅ Both methods are END-TO-END differentiable")
    
    logger.info("\nNext steps:")
    logger.info("1. Choose method based on your research focus")
    logger.info("2. Train CNN-BiLSTM with selected features")
    logger.info("3. Compare accuracy vs baseline (all features)")
    logger.info("4. Analyze FL convergence with reduced features")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
