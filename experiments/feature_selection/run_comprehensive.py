"""
Comprehensive Feature Selection: All Methods

Runs ALL feature selection methods and generates detailed markdown report.
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
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs.feature_selection import (
    FeatureSelector, compare_selection_methods
)
from projects.shared_libs.rl_feature_selection import train_rl_feature_selector
from projects.shared_libs.dnn_feature_selection import train_dnn_feature_selector
from sklearn.model_selection import train_test_split


def generate_markdown_report(all_results, feature_names, target_features, output_file):
    """Generate comprehensive markdown report"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Header
        f.write("# Comprehensive Feature Selection Report\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Target Features**: {target_features}\n")
        f.write(f"**Original Features**: {len(feature_names) if feature_names else 'N/A'}\n\n")
        
        f.write("---\n\n")
        
        # Executive Summary
        f.write("## Executive Summary\n\n")
        f.write("This report compares **7 feature selection methods** across traditional statistical, ")
        f.write("machine learning, and deep learning approaches for DDoS detection.\n\n")
        
        f.write("### Methods Evaluated\n\n")
        f.write("| Method | Type | Novelty | Computational Cost |\n")
        f.write("|--------|------|---------|--------------------|\n")
        f.write("| **Mutual Information** | Statistical | Low | Very Low |\n")
        f.write("| **ANOVA F-Test** | Statistical | Low | Very Low |\n")
        f.write("| **Random Forest** | ML-based | Low | Medium |\n")
        f.write("| **Ensemble (MI+ANOVA+RF)** | Voting | Low | Medium |\n")
        f.write("| **RL (Deep Q-Learning)** | Reinforcement Learning | **Very High** | High |\n")
        f.write("| **DNN Attention** | Deep Learning | **High** | Medium-High |\n")
        f.write("| **DNN Concrete Selector** | Deep Learning | **High** | Medium-High |\n\n")
        
        # Performance Summary Table
        f.write("## Performance Summary\n\n")
        f.write("| Method | Features Selected | Execution Time | Status |\n")
        f.write("|--------|------------------|----------------|--------|\n")
        
        for method, result in all_results.items():
            num_feats = result.get('num_features', len(result.get('indices', [])))
            time_str = f"{result.get('time', 0):.2f}s"
            status = "✅" if result.get('success', True) else "❌"
            f.write(f"| {method} | {num_feats} | {time_str} | {status} |\n")
        
        f.write("\n---\n\n")
        
        # Detailed Results for Each Method
        f.write("## Detailed Method Results\n\n")
        
        for method, result in all_results.items():
            f.write(f"### {method.upper()}\n\n")
            
            if not result.get('success', True):
                f.write(f"**Status**: ❌ Failed\n\n")
                f.write(f"**Error**: {result.get('error', 'Unknown error')}\n\n")
                continue
            
            indices = result.get('indices', [])
            num_feats = len(indices)
            exec_time = result.get('time', 0)
            
            f.write(f"**Features Selected**: {num_feats}/{len(feature_names) if feature_names else 'N/A'}\n\n")
            f.write(f"**Execution Time**: {exec_time:.2f} seconds ({exec_time/60:.2f} minutes)\n\n")
            
            # Top 20 selected features
            f.write(f"**Selected Feature Indices** (first 20):\n```\n")
            f.write(f"{sorted(indices)[:20]}\n")
            f.write(f"```\n\n")
            
            if feature_names and len(indices) > 0:
                f.write(f"**Selected Feature Names** (first 15):\n")
                for idx in sorted(indices)[:15]:
                    if idx < len(feature_names):
                        f.write(f"- {feature_names[idx]} (index {idx})\n")
                f.write("\n")
            
            # Method-specific notes
            if method == 'mutual_information':
                f.write("**Notes**: Measures dependency between features and target. Good for non-linear relationships.\n\n")
            elif method == 'anova_f':
                f.write("**Notes**: Measures linear correlation using F-statistic. Fast and interpretable.\n\n")
            elif method == 'random_forest':
                f.write("**Notes**: Uses Gini importance from Random Forest. Captures feature interactions.\n\n")
            elif method == 'ensemble':
                f.write("**Notes**: Consensus voting across MI + ANOVA + RF. Most robust traditional method.\n\n")
            elif method == 'rl_dqn':
                f.write("**Notes**: ⭐ **NOVEL** - Deep Q-Network learns optimal feature policy via reinforcement learning.\n\n")
            elif method == 'dnn_attention':
                f.write("**Notes**: ⭐ **NOVEL** - Attention mechanism learns continuous importance weights. End-to-end differentiable.\n\n")
            elif method == 'dnn_concrete':
                f.write("**Notes**: ⭐ **NOVEL** - Learnable binary gates with Gumbel-Softmax. Hard feature selection.\n\n")
            
            f.write("---\n\n")
        
        # Feature Overlap Analysis
        f.write("## Feature Overlap Analysis\n\n")
        f.write("Analyzing consensus across methods:\n\n")
        
        # Compute overlaps
        methods = list(all_results.keys())
        f.write("| Method 1 | Method 2 | Overlap | Overlap % |\n")
        f.write("|----------|----------|---------|----------|\n")
        
        for i, method1 in enumerate(methods):
            if not all_results[method1].get('success', True):
                continue
            for method2 in methods[i+1:]:
                if not all_results[method2].get('success', True):
                    continue
                    
                set1 = set(all_results[method1]['indices'])
                set2 = set(all_results[method2]['indices'])
                overlap = len(set1 & set2)
                overlap_pct = (overlap / target_features) * 100 if target_features > 0 else 0
                
                f.write(f"| {method1} | {method2} | {overlap}/{target_features} | {overlap_pct:.1f}% |\n")
        
        f.write("\n")
        
        # Consensus Features
        f.write("### Consensus Features\n\n")
        f.write("Features selected by **ALL methods**:\n\n")
        
        # Get intersection of all methods
        all_indices = [set(result['indices']) for result in all_results.values() 
                      if result.get('success', True) and 'indices' in result]
        
        if all_indices:
            consensus = set.intersection(*all_indices)
            f.write(f"**Count**: {len(consensus)} features\n\n")
            
            if consensus:
                f.write(f"**Indices**: {sorted(list(consensus))}\n\n")
                
                if feature_names:
                    f.write("**Feature Names**:\n")
                    for idx in sorted(list(consensus)):
                        if idx < len(feature_names):
                            f.write(f"- {feature_names[idx]}\n")
                    f.write("\n")
            else:
                f.write("*No features selected by ALL methods*\n\n")
        
        # Features selected by majority (>=50% methods)
        f.write("### Majority Features (≥50% of methods)\n\n")
        
        feature_vote_count = {}
        for result in all_results.values():
            if result.get('success', True) and 'indices' in result:
                for idx in result['indices']:
                    feature_vote_count[idx] = feature_vote_count.get(idx, 0) + 1
        
        num_methods = len([r for r in all_results.values() if r.get('success', True)])
        majority_threshold = num_methods // 2
        
        majority_features = {idx: count for idx, count in feature_vote_count.items() 
                           if count >= majority_threshold}
        
        f.write(f"**Count**: {len(majority_features)} features (voted by ≥{majority_threshold}/{num_methods} methods)\n\n")
        
        if majority_features:
            # Sort by vote count
            sorted_majority = sorted(majority_features.items(), key=lambda x: x[1], reverse=True)
            
            f.write("| Feature Index | Feature Name | Votes |\n")
            f.write("|--------------|--------------|-------|\n")
            
            for idx, votes in sorted_majority[:20]:  # Top 20
                fname = feature_names[idx] if feature_names and idx < len(feature_names) else f"Feature_{idx}"
                f.write(f"| {idx} | {fname} | {votes}/{num_methods} |\n")
            
            f.write("\n")
        
        f.write("---\n\n")
        
        # Recommendations
        f.write("## Recommendations\n\n")
        
        f.write("### For Research Paper\n\n")
        f.write("**Recommended Method**: **Ensemble** or **DNN Concrete Selector**\n\n")
        f.write("**Rationale**:\n")
        f.write("- **Ensemble**: Robust consensus across traditional methods, reliable baseline\n")
        f.write("- **DNN Concrete**: Novel approach, end-to-end learnable, good for deep learning pipelines\n\n")
        
        f.write("### For Production Deployment\n\n")
        f.write("**Recommended Method**: **Random Forest** or **DNN Attention**\n\n")
        f.write("**Rationale**:\n")
        f.write("- **Random Forest**: Fast, proven, interpretable importance scores\n")
        f.write("- **DNN Attention**: Integrated with model training, continuous importance weights\n\n")
        
        f.write("### For Novel Research Contribution\n\n")
        f.write("**Recommended Methods**: **RL (DQN)**, **DNN Attention**, **DNN Concrete**\n\n")
        f.write("**Rationale**:\n")
        f.write("- ⭐ **First application** of RL-based feature selection to FL-DDoS detection\n")
        f.write("- ⭐ **Novel** attention and Gumbel-Softmax approaches for network security\n")
        f.write("- ⭐ **End-to-end differentiable** - integrated with model optimization\n\n")
        
        f.write("---\n\n")
        
        # Next Steps
        f.write("## Next Steps\n\n")
        f.write("1. **Choose a method** based on your research focus\n")
        f.write("2. **Load selected features**:\n")
        f.write("   ```python\n")
        f.write("   import pickle\n")
        f.write("   with open('data/processed/comprehensive_feature_selection.pkl', 'rb') as f:\n")
        f.write("       results = pickle.load(f)\n")
        f.write("   selected_indices = results['ensemble']['indices']  # Or any method\n")
        f.write("   ```\n")
        f.write("3. **Train CNN-BiLSTM** with selected features:\n")
        f.write("   ```bash\n")
        f.write("   python train_with_selected_features.py\n")
        f.write("   ```\n")
        f.write("4. **Compare performance**: Baseline (all features) vs Selected features\n\n")
        
        f.write("---\n\n")
        f.write("*Report generated by Comprehensive Feature Selection System*\n")
    
    logger.info(f"Report saved to: {output_file}")


def main():
    """Run comprehensive feature selection across all methods"""
    logger.info("\n" + "📊"*35)
    logger.info("Comprehensive Feature Selection: ALL Methods")
    logger.info("📊"*35 + "\n")
    
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
    feature_names = None
    extractor_file = Path("data/processed/cicddos2019_full_feature_extractor.pkl")
    if extractor_file.exists():
        with open(extractor_file, 'rb') as f:
            extractor_data = pickle.load(f)
            feature_names = extractor_data.get('feature_names', None)
    
    # Configuration
    target_features = 40
    logger.info(f"\nTarget: Select {target_features} features from {X.shape[1]}")
    
    # Split for validation
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Sample for traditional methods (faster)
    sample_size = min(10000, len(X_train))
    sample_idx = np.random.choice(len(X_train), sample_size, replace=False)
    X_sample, y_sample = X_train[sample_idx], y_train[sample_idx]
    
    all_results = {}
    
    # === TRADITIONAL METHODS ===
    
    logger.info("\n" + "="*70)
    logger.info("TRADITIONAL STATISTICAL & ML METHODS")
    logger.info("="*70)
    
    selector = FeatureSelector()
    
    # 1. Mutual Information
    logger.info("\n1/7: Mutual Information")
    try:
        start = time.time()
        _, mi_indices = selector.mutual_information_selection(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        elapsed = time.time() - start
        all_results['mutual_information'] = {
            'indices': mi_indices,
            'num_features': len(mi_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"Mutual Information failed: {e}")
        all_results['mutual_information'] = {'success': False, 'error': str(e)}
    
    # 2. ANOVA F-test
    logger.info("\n2/7: ANOVA F-Test")
    try:
        start = time.time()
        _, anova_indices = selector.correlation_based_selection(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        elapsed = time.time() - start
        all_results['anova_f'] = {
            'indices': anova_indices,
            'num_features': len(anova_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"ANOVA F-test failed: {e}")
        all_results['anova_f'] = {'success': False, 'error': str(e)}
    
    # 3. Random Forest Importance
    logger.info("\n3/7: Random Forest Importance")
    try:
        start = time.time()
        _, rf_indices = selector.random_forest_importance(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        elapsed = time.time() - start
        all_results['random_forest'] = {
            'indices': rf_indices,
            'num_features': len(rf_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"Random Forest failed: {e}")
        all_results['random_forest'] = {'success': False, 'error': str(e)}
    
    # 4. Ensemble (Voting)
    logger.info("\n4/7: Ensemble (MI + ANOVA + RF)")
    try:
        start = time.time()
        _, ensemble_indices = selector.ensemble_selection(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        elapsed = time.time() - start
        all_results['ensemble'] = {
            'indices': ensemble_indices,
            'num_features': len(ensemble_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"Ensemble failed: {e}")
        all_results['ensemble'] = {'success': False, 'error': str(e)}
    
    # === ADVANCED METHODS (RL & DNN) ===
    
    logger.info("\n" + "="*70)
    logger.info("ADVANCED RL & DEEP LEARNING METHODS")
    logger.info("="*70)
    
    # 5. RL (Deep Q-Learning)
    logger.info("\n5/7: RL (Deep Q-Learning)")
    try:
        start = time.time()
        rl_indices, _ = train_rl_feature_selector(
            X_train, y_train,
            max_features=target_features,
            num_episodes=50
        )
        elapsed = time.time() - start
        all_results['rl_dqn'] = {
            'indices': rl_indices,
            'num_features': len(rl_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"RL failed: {e}", exc_info=True)
        all_results['rl_dqn'] = {'success': False, 'error': str(e)}
    
    # 6. DNN Attention
    logger.info("\n6/7: DNN Attention Mechanism")
    try:
        start = time.time()
        attention_indices, _ = train_dnn_feature_selector(
            X_train, y_train, X_val, y_val,
            method='attention',
            num_epochs=20,
            top_k=target_features
        )
        elapsed = time.time() - start
        all_results['dnn_attention'] = {
            'indices': attention_indices,
            'num_features': len(attention_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"DNN Attention failed: {e}", exc_info=True)
        all_results['dnn_attention'] = {'success': False, 'error': str(e)}
    
    # 7. DNN Concrete Selector
    logger.info("\n7/7: DNN Concrete Selector (Gumbel-Softmax)")
    try:
        start = time.time()
        concrete_indices, _ = train_dnn_feature_selector(
            X_train, y_train, X_val, y_val,
            method='concrete',
            num_epochs=20,
            top_k=target_features
        )
        elapsed = time.time() - start
        all_results['dnn_concrete'] = {
            'indices': concrete_indices,
            'num_features': len(concrete_indices),
            'time': elapsed,
            'success': True
        }
    except Exception as e:
        logger.error(f"DNN Concrete failed: {e}", exc_info=True)
        all_results['dnn_concrete'] = {'success': False, 'error': str(e)}
    
    # Save results
    logger.info("\n" + "="*70)
    logger.info("SAVING RESULTS")
    logger.info("="*70)
    
    output_dir = Path("data/processed")
    
    # Save pickle
    pkl_file = output_dir / "comprehensive_feature_selection.pkl"
    with open(pkl_file, 'wb') as f:
        pickle.dump(all_results, f)
    logger.info(f"Saved results (pickle): {pkl_file}")
    
    # Generate markdown report
    md_file = output_dir / "FEATURE_SELECTION_REPORT.md"
    generate_markdown_report(all_results, feature_names, target_features, md_file)
    
    # Summary
    logger.info("\n" + "✅"*35)
    logger.info("COMPREHENSIVE FEATURE SELECTION COMPLETE!")
    logger.info("✅"*35)
    
    successful = sum(1 for r in all_results.values() if r.get('success', True))
    logger.info(f"\nSuccessful methods: {successful}/{len(all_results)}")
    
    logger.info(f"\nResults saved:")
    logger.info(f"  1. Pickle: {pkl_file}")
    logger.info(f"  2. Report: {md_file}")
    
    logger.info(f"\nView report: cat {md_file}")
    logger.info(f"Or open in editor to see detailed analysis")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
