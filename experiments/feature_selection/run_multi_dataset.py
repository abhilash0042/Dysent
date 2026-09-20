"""
Unified Feature Selection for Multiple Datasets

Runs comprehensive feature selection (all 10 methods) on both:
- CICDDoS2019 dataset
- NSL-KDD dataset

Generates separate feature selection reports for each dataset.
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs.feature_selection import FeatureSelector
from projects.shared_libs.rl_feature_selection import train_rl_feature_selector
from projects.shared_libs.dnn_feature_selection import train_dnn_feature_selector
from projects.shared_libs.advanced_feature_selection import (
    shap_feature_selection,
    genetic_algorithm_feature_selection,
    boruta_feature_selection
)
from sklearn.model_selection import train_test_split


def load_dataset(dataset_name):
    """Load processed dataset"""
    processed_dir = Path("data/processed")
    
    if dataset_name == 'cicddos2019':
        data_file = processed_dir / "cicddos2019_full_processed.npz"
        extractor_file = processed_dir / "cicddos2019_full_feature_extractor.pkl"
    elif dataset_name == 'nslkdd':
        data_file = processed_dir / "nslkdd_full_processed.npz"
        extractor_file = processed_dir / "nslkdd_full_feature_extractor.pkl"
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")
    
    if not data_file.exists():
        logger.error(f"Dataset not found: {data_file}")
        return None, None
    
    # Load data
    data = np.load(data_file)
    X, y = data['X'], data['y']
    
    # Load feature names
    feature_names = None
    if extractor_file.exists():
        with open(extractor_file, 'rb') as f:
            extractor_data = pickle.load(f)
            feature_names = extractor_data.get('feature_names', None)
    
    logger.info(f"Loaded {dataset_name}: {X.shape[0]:,} samples, {X.shape[1]} features")
    
    return (X, y, feature_names), data_file.stem


def run_all_feature_selection_methods(X, y, feature_names, target_features, dataset_name):
    """Run all 10 feature selection methods"""
    
    logger.info("\n" + "="*70)
    logger.info(f"DATASET: {dataset_name.upper()}")
    logger.info(f"Shape: {X.shape}, Target features: {target_features}")
    logger.info("="*70)
    
    # Split for validation
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Sample for traditional methods
    sample_size = min(10000, len(X_train))
    sample_idx = np.random.choice(len(X_train), sample_size, replace=False)
    X_sample, y_sample = X_train[sample_idx], y_train[sample_idx]
    
    all_results = {}
    
    # === TRADITIONAL METHODS ===
    logger.info("\n" + "🔹"*35)
    logger.info("TRADITIONAL METHODS (1-4)")
    logger.info("🔹"*35)
    
    selector = FeatureSelector()
    
    # 1. Mutual Information
    logger.info("\n✓ 1/10: Mutual Information")
    try:
        start = time.time()
        _, mi_indices = selector.mutual_information_selection(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        all_results['mutual_information'] = {
            'indices': mi_indices,
            'num_features': len(mi_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"MI failed: {e}")
        all_results['mutual_information'] = {'success': False, 'error': str(e)}
    
    # 2. ANOVA F-test
    logger.info("\n✓ 2/10: ANOVA F-Test")
    try:
        start = time.time()
        _, anova_indices = selector.correlation_based_selection(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        all_results['anova_f'] = {
            'indices': anova_indices,
            'num_features': len(anova_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"ANOVA failed: {e}")
        all_results['anova_f'] = {'success': False, 'error': str(e)}
    
    # 3. Random Forest
    logger.info("\n✓ 3/10: Random Forest")
    try:
        start = time.time()
        _, rf_indices = selector.random_forest_importance(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        all_results['random_forest'] = {
            'indices': rf_indices,
            'num_features': len(rf_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"RF failed: {e}")
        all_results['random_forest'] = {'success': False, 'error': str(e)}
    
    # 4. Ensemble
    logger.info("\n✓ 4/10: Ensemble")
    try:
        start = time.time()
        _, ensemble_indices = selector.ensemble_selection(
            X_sample, y_sample, top_k=target_features, feature_names=feature_names
        )
        all_results['ensemble'] = {
            'indices': ensemble_indices,
            'num_features': len(ensemble_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"Ensemble failed: {e}")
        all_results['ensemble'] = {'success': False, 'error': str(e)}
    
    # === ADVANCED RL/DNN METHODS ===
    logger.info("\n" + "🔹"*35)
    logger.info("RL & DNN METHODS (5-7)")
    logger.info("🔹"*35)
    
    # 5. RL DQN
    logger.info("\n✓ 5/10: RL (Deep Q-Learning)")
    try:
        start = time.time()
        rl_indices, _ = train_rl_feature_selector(
            X_train, y_train, max_features=target_features, num_episodes=30  # Reduced for speed
        )
        all_results['rl_dqn'] = {
            'indices': rl_indices,
            'num_features': len(rl_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"RL failed: {e}")
        all_results['rl_dqn'] = {'success': False, 'error': str(e)}
    
    # 6. DNN Attention
    logger.info("\n✓ 6/10: DNN Attention")
    try:
        start = time.time()
        attention_indices, _ = train_dnn_feature_selector(
            X_train, y_train, X_val, y_val,
            method='attention', num_epochs=15, top_k=target_features  # Reduced for speed
        )
        all_results['dnn_attention'] = {
            'indices': attention_indices,
            'num_features': len(attention_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"DNN Attention failed: {e}")
        all_results['dnn_attention'] = {'success': False, 'error': str(e)}
    
    # 7. DNN Concrete
    logger.info("\n✓ 7/10: DNN Concrete Selector")
    try:
        start = time.time()
        concrete_indices, _ = train_dnn_feature_selector(
            X_train, y_train, X_val, y_val,
            method='concrete', num_epochs=15, top_k=target_features  # Reduced for speed
        )
        all_results['dnn_concrete'] = {
            'indices': concrete_indices,
            'num_features': len(concrete_indices),
            'time': time.time() - start,
            'success': True
        }
    except Exception as e:
        logger.error(f"DNN Concrete failed: {e}")
        all_results['dnn_concrete'] = {'success': False, 'error': str(e)}
    
    # === ADVANCED ML METHODS ===
    logger.info("\n" + "🔹"*35)
    logger.info("ADVANCED ML METHODS (8-10)")
    logger.info("🔹"*35)
    
    # 8. SHAP
    logger.info("\n✓ 8/10: SHAP")
    try:
        start = time.time()
        shap_indices, shap_meta = shap_feature_selection(
            X_sample, y_sample, top_k=target_features
        )
        all_results['shap'] = {
            'indices': shap_indices,
            'num_features': len(shap_indices),
            'time': time.time() - start,
            **shap_meta
        }
    except Exception as e:
        logger.error(f"SHAP failed: {e}")
        all_results['shap'] = {'success': False, 'error': str(e)}
    
    # 9. Genetic Algorithm
    logger.info("\n✓ 9/10: Genetic Algorithm")
    try:
        start = time.time()
        ga_indices, ga_meta = genetic_algorithm_feature_selection(
            X_sample, y_sample, top_k=target_features,
            generations=15, population_size=30  # Reduced for speed
        )
        all_results['genetic_algorithm'] = {
            'indices': ga_indices,
            'num_features': len(ga_indices),
            'time': time.time() - start,
            **ga_meta
        }
    except Exception as e:
        logger.error(f"GA failed: {e}")
        all_results['genetic_algorithm'] = {'success': False, 'error': str(e)}
    
    # 10. Boruta
    logger.info("\n✓ 10/10: Boruta")
    try:
        start = time.time()
        boruta_indices, boruta_meta = boruta_feature_selection(
            X_sample, y_sample, top_k=target_features, max_iter=50  # Reduced for speed
        )
        all_results['boruta'] = {
            'indices': boruta_indices,
            'num_features': len(boruta_indices),
            'time': time.time() - start,
            **boruta_meta
        }
    except Exception as e:
        logger.error(f"Boruta failed: {e}")
        all_results['boruta'] = {'success': False, 'error': str(e)}
    
    return all_results


def generate_comparison_report(results_by_dataset, output_file):
    """Generate markdown comparison report for both datasets"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Multi-Dataset Feature Selection Comparison\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        # Summary table
        f.write("## Summary by Dataset\n\n")
        
        for dataset_name, results in results_by_dataset.items():
            f.write(f"### {dataset_name.upper()}\n\n")
            f.write("| Method | Features | Time (s) | Status |\n")
            f.write("|--------|----------|----------|--------|\n")
            
            for method, result in results.items():
                num_feat = result.get('num_features', len(result.get('indices', [])))
                time_val = result.get('time', 0)
                status = "✅" if result.get('success', True) else "❌"
                f.write(f"| {method} | {num_feat} | {time_val:.2f} | {status} |\n")
            
            f.write("\n")
        
        # Dataset comparison
        f.write("## Dataset Comparison\n\n")
        
        datasets = list(results_by_dataset.keys())
        if len(datasets) == 2:
            f.write(f"Comparing **{datasets[0]}** vs **{datasets[1]}**\n\n")
            
            methods = list(results_by_dataset[datasets[0]].keys())
            
            f.write("| Method | Dataset 1 Features | Dataset 2 Features | Overlap |\n")
            f.write("|--------|-------------------|-------------------|----------|\n")
            
            for method in methods:
                r1 = results_by_dataset[datasets[0]].get(method, {})
                r2 = results_by_dataset[datasets[1]].get(method, {})
                
                if r1.get('success') and r2.get('success'):
                    indices1 = set(r1.get('indices', []))
                    indices2 = set(r2.get('indices', []))
                    
                    # Note: Can't compute overlap directly as indices reference different features
                    f.write(f"| {method} | {len(indices1)} | {len(indices2)} | N/A* |\n")
            
            f.write("\n*Overlap not applicable - different feature spaces\n\n")
        
        f.write("---\n\n")
        f.write("*Report generated by Multi-Dataset Feature Selection System*\n")
    
    logger.info(f"Report saved to: {output_file}")


def main():
    """Run feature selection on all available datasets"""
    logger.info("\n" + "🌍"*35)
    logger.info("Multi-Dataset Feature Selection")
    logger.info("🌍"*35 + "\n")
    
    # Detect available datasets
    datasets_to_process = []
    
    cicddos_data = load_dataset('cicddos2019')
    if cicddos_data[0] is not None:
        datasets_to_process.append(('cicddos2019', cicddos_data))
    
    try:
        nslkdd_data = load_dataset('nslkdd')
        if nslkdd_data[0] is not None:
            datasets_to_process.append(('nslkdd', nslkdd_data))
    except:
        logger.warning("NSL-KDD dataset not found, skipping...")
    
    if not datasets_to_process:
        logger.error("No datasets found! Please run load_dataset.py first")
        return 1
    
    logger.info(f"\nFound {len(datasets_to_process)} dataset(s) to process")
    
    # Configuration
    target_features = 40
    logger.info(f"Target: Select {target_features} features from each dataset\n")
    
    results_by_dataset = {}
    
    # Process each dataset
    for dataset_name, ((X, y, feature_names), file_stem) in datasets_to_process:
        logger.info("\n" + "="*70)
        logger.info(f"Processing: {dataset_name.upper()}")
        logger.info("="*70)
        
        results = run_all_feature_selection_methods(
            X, y, feature_names, target_features, dataset_name
        )
        
        results_by_dataset[dataset_name] = results
        
        # Save individual dataset results
        output_dir = Path("data/processed")
        pkl_file = output_dir / f"{file_stem}_feature_selection.pkl"
        
        with open(pkl_file, 'wb') as f:
            pickle.dump(results, f)
        
        logger.info(f"\nSaved {dataset_name} results to: {pkl_file}")
    
    # Generate comparison report
    report_file = Path("data/processed") / "MULTI_DATASET_FEATURE_SELECTION.md"
    generate_comparison_report(results_by_dataset, report_file)
    
    # Summary
    logger.info("\n" + "✅"*35)
    logger.info("MULTI-DATASET FEATURE SELECTION COMPLETE!")
    logger.info("✅"*35)
    
    logger.info(f"\nProcessed {len(datasets_to_process)} dataset(s)")
    logger.info(f"Results saved to: data/processed/")
    logger.info(f"Comparison report: {report_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
