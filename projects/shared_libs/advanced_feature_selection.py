"""
Additional Advanced Feature Selection Methods

Implements SHAP, Genetic Algorithm, and Boruta feature selection methods.
"""

import numpy as np
import logging
from typing import List, Tuple, Optional
import time

logger = logging.getLogger(__name__)


def shap_feature_selection(
    X: np.ndarray,
    y: np.ndarray,
    top_k: int = 40,
    model_type: str = 'xgboost',
    max_samples: int = 1000
) -> Tuple[List[int], dict]:
    """
    Feature selection using SHAP (SHapley Additive exPlanations)
    
    SHAP provides model-agnostic feature importance based on game theory.
    
    Args:
        X: Features
        y: Labels
        top_k: Number of features to select
        model_type: 'xgboost', 'lightgbm', or 'random_forest'
        max_samples: Max samples for SHAP computation (for speed)
        
    Returns:
        Tuple of (selected feature indices, metadata dict)
    """
    logger.info("="*70)
    logger.info(f"SHAP Feature Selection (Model: {model_type})")
    logger.info("="*70)
    
    try:
        import shap
        import xgboost as xgb
    except ImportError:
        logger.error("SHAP or XGBoost not installed. Install with: pip install shap xgboost")
        return [], {'success': False, 'error': 'Missing dependencies'}
    
    # Sample data if too large
    if len(X) > max_samples:
        logger.info(f"Sampling {max_samples} records for SHAP computation...")
        sample_idx = np.random.choice(len(X), max_samples, replace=False)
        X_sample, y_sample = X[sample_idx], y[sample_idx]
    else:
        X_sample, y_sample = X, y
    
    # Train model
    logger.info(f"Training {model_type} model...")
    
    if model_type == 'xgboost':
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
    else:
        from sklearn.ensemble import RandomForestClassifier
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
    
    model.fit(X_sample, y_sample)
    
    # Compute SHAP values
    logger.info("Computing SHAP values...")
    
    if model_type == 'xgboost':
        explainer = shap.TreeExplainer(model)
    else:
        explainer = shap.Explainer(model, X_sample)
    
    shap_values = explainer.shap_values(X_sample)
    
    # Handle multi-class output
    if isinstance(shap_values, list):
        # Average across classes
        shap_values = np.mean([np.abs(sv) for sv in shap_values], axis=0)
    else:
        shap_values = np.abs(shap_values)
    
    # Compute feature importance (mean absolute SHAP)
    if len(shap_values.shape) > 2:
        importance = np.mean(np.abs(shap_values), axis=(0, 1))
    else:
        importance = np.mean(np.abs(shap_values), axis=0)
    
    # Select top k features
    selected_indices = np.argsort(importance)[-top_k:][::-1].tolist()
    
    logger.info(f"Selected {len(selected_indices)} features using SHAP")
    logger.info(f"Top 10 features by SHAP importance:")
    for i, idx in enumerate(selected_indices[:10], 1):
        logger.info(f"  {i}. Feature {idx}: {importance[idx]:.4f}")
    
    metadata = {
        'success': True,
        'method': 'shap',
        'model_type': model_type,
        'importance_scores': importance.tolist()
    }
    
    return selected_indices, metadata


def genetic_algorithm_feature_selection(
    X: np.ndarray,
    y: np.ndarray,
    top_k: int = 40,
    generations: int = 20,
    population_size: int = 50,
    crossover_prob: float = 0.8,
    mutation_prob: float = 0.1
) -> Tuple[List[int], dict]:
    """
    Feature selection using Genetic Algorithm
    
    Evolves feature subsets using genetic operators: selection, crossover, mutation.
    
    Args:
        X: Features
        y: Labels
        top_k: Number of features to select
        generations: Number of GA generations
        population_size: Size of population
        crossover_prob: Probability of crossover
        mutation_prob: Probability of mutation
        
    Returns:
        Tuple of (selected feature indices, metadata dict)
    """
    logger.info("="*70)
    logger.info("Genetic Algorithm Feature Selection")
    logger.info("="*70)
    
    try:
        from sklearn_genetic import GAFeatureSelectionCV
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        logger.error("sklearn-genetic-opt not installed. Install with: pip install sklearn-genetic-opt")
        return [], {'success': False, 'error': 'Missing sklearn-genetic-opt'}
    
    logger.info(f"GA Parameters:")
    logger.info(f"  Generations: {generations}")
    logger.info(f"  Population: {population_size}")
    logger.info(f"  Crossover prob: {crossover_prob}")
    logger.info(f"  Mutation prob: {mutation_prob}")
    
    # Sample for speed
    max_samples = min(10000, len(X))
    if len(X) > max_samples:
        logger.info(f"Sampling {max_samples} records for GA...")
        sample_idx = np.random.choice(len(X), max_samples, replace=False)
        X_sample, y_sample = X[sample_idx], y[sample_idx]
    else:
        X_sample, y_sample = X, y
    
    # Create GA selector
    estimator = RandomForestClassifier(
        n_estimators=50,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    
    selector = GAFeatureSelectionCV(
        estimator=estimator,
        cv=3,
        generations=generations,
        population_size=population_size,
        crossover_probability=crossover_prob,
        mutation_probability=mutation_prob,
        n_jobs=-1,
        verbose=True,
        scoring='accuracy'
    )
    
    logger.info("Evolving feature subsets...")
    selector.fit(X_sample, y_sample)
    
    # Get selected features
    selected_mask = selector.support_
    selected_indices = np.where(selected_mask)[0].tolist()
    
    # If more than top_k selected, use feature importances to trim
    if len(selected_indices) > top_k:
        logger.info(f"GA selected {len(selected_indices)} features, trimming to {top_k}...")
        # Train RF  on selected features to get importance
        rf = RandomForestClassifier(n_estimators=50, random_state=42)
        rf.fit(X_sample[:, selected_indices], y_sample)
        importance = rf.feature_importances_
        
        # Select top k by importance
        top_k_mask = np.argsort(importance)[-top_k:]
        selected_indices = [selected_indices[i] for i in top_k_mask]
    
    logger.info(f"Selected {len(selected_indices)} features using GA")
    logger.info(f"Best fitness score: {selector.best_score_:.4f}")
    
    metadata = {
        'success': True,
        'method': 'genetic_algorithm',
        'best_score': float(selector.best_score_),
        'generations': generations,
        'final_population_size': population_size
    }
    
    return selected_indices, metadata


def boruta_feature_selection(
    X: np.ndarray,
    y: np.ndarray,
    top_k: Optional[int] = None,
    max_iter: int = 100,
    perc: int = 100,
    alpha: float = 0.05
) -> Tuple[List[int], dict]:
    """
    Feature selection using Boruta algorithm
    
    Boruta is an all-relevant feature selection method that finds ALL features
    that are statistically relevant, not just top-k.
    
    Args:
        X: Features
        y: Labels
        top_k: Optional, limit to top k (if None, returns all relevant)
        max_iter: Maximum iterations
        perc: Percentile for shadow features
        alpha: Significance level
        
    Returns:
        Tuple of (selected feature indices, metadata dict)
    """
    logger.info("="*70)
    logger.info("Boruta Feature Selection (All-Relevant)")
    logger.info("="*70)
    
    try:
        from boruta import BorutaPy
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        logger.error("Boruta not installed. Install with: pip install Boruta")
        return [], {'success': False, 'error': 'Missing Boruta package'}
    
    logger.info(f"Boruta Parameters:")
    logger.info(f"  Max iterations: {max_iter}")
    logger.info(f"  Percentile: {perc}")
    logger.info(f"  Significance (alpha): {alpha}")
    
    # Sample for speed
    max_samples = min(10000, len(X))
    if len(X) > max_samples:
        logger.info(f"Sampling {max_samples} records for Boruta...")
        sample_idx = np.random.choice(len(X), max_samples, replace=False)
        X_sample, y_sample = X[sample_idx], y[sample_idx]
    else:
        X_sample, y_sample = X, y
    
    # Create RF estimator
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=7,
        n_jobs=-1,
        random_state=42
    )
    
    # Create Boruta selector
    boruta = BorutaPy(
        estimator=rf,
        n_estimators='auto',
        max_iter=max_iter,
        perc=perc,
        alpha=alpha,
        verbose=2,
        random_state=42
    )
    
    logger.info("Running Boruta algorithm...")
    logger.info("This finds ALL relevant features (may take several minutes)...")
    
    boruta.fit(X_sample, y_sample)
    
    # Get selected features
    selected_mask = boruta.support_
    selected_indices = np.where(selected_mask)[0].tolist()
    
    # Also get tentative features
    tentative_mask = boruta.support_weak_
    tentative_indices = np.where(tentative_mask)[0].tolist()
    
    logger.info(f"\nBoruta Results:")
    logger.info(f"  Confirmed features: {len(selected_indices)}")
    logger.info(f"  Tentative features: {len(tentative_indices)}")
    logger.info(f"  Rejected features: {X.shape[1] - len(selected_indices) - len(tentative_indices)}")
    
    # If top_k specified and we have more features, use ranking to select top k
    if top_k and len(selected_indices) > top_k:
        logger.info(f"Trimming {len(selected_indices)} features to top {top_k}...")
        ranking = boruta.ranking_
        
        # Lower rank = more important
        selected_rankings = [(idx, ranking[idx]) for idx in selected_indices]
        selected_rankings.sort(key=lambda x: x[1])
        
        selected_indices = [idx for idx, _ in selected_rankings[:top_k]]
    elif top_k and len(selected_indices) < top_k:
        # Add tentative features if needed
        logger.info(f"Only {len(selected_indices)} confirmed, adding tentative to reach {top_k}...")
        needed = top_k - len(selected_indices)
        selected_indices.extend(tentative_indices[:needed])
    
    logger.info(f"Final selection: {len(selected_indices)} features")
    
    # Get iterations completed (attribute name varies by Boruta version)
    iterations = max_iter  # Default fallback
    if hasattr(boruta, 'n_iter_'):
        iterations = boruta.n_iter_
    elif hasattr(boruta, 'n_iter'):
        iterations = boruta.n_iter
    elif hasattr(boruta, 'n_features_'):
        # Some versions don't track iterations
        iterations = max_iter
    
    metadata = {
        'success': True,
        'method': 'boruta',
        'confirmed_features': len(np.where(boruta.support_)[0]),
        'tentative_features': len(tentative_indices),
        'iterations_completed': iterations
    }
    
    return selected_indices, metadata


# Convenience function to run all three
def run_advanced_methods(
    X: np.ndarray,
    y: np.ndarray,
    top_k: int = 40
) -> dict:
    """
    Run SHAP, Genetic Algorithm, and Boruta feature selection
    
    Args:
        X: Features
        y: Labels
        top_k: Number of features to select
        
    Returns:
        Dictionary with results from all three methods
    """
    results = {}
    
    # SHAP
    logger.info("\n" + "="*70)
    logger.info("METHOD 1/3: SHAP")
    logger.info("="*70)
    try:
        start = time.time()
        shap_indices, shap_meta = shap_feature_selection(X, y, top_k)
        elapsed = time.time() - start
        
        results['shap'] = {
            'indices': shap_indices,
            'num_features': len(shap_indices),
            'time': elapsed,
            **shap_meta
        }
    except Exception as e:
        logger.error(f"SHAP failed: {e}", exc_info=True)
        results['shap'] = {'success': False, 'error': str(e)}
    
    # Genetic Algorithm
    logger.info("\n" + "="*70)
    logger.info("METHOD 2/3: Genetic Algorithm")
    logger.info("="*70)
    try:
        start = time.time()
        ga_indices, ga_meta = genetic_algorithm_feature_selection(X, y, top_k)
        elapsed = time.time() - start
        
        results['genetic_algorithm'] = {
            'indices': ga_indices,
            'num_features': len(ga_indices),
            'time': elapsed,
            **ga_meta
        }
    except Exception as e:
        logger.error(f"Genetic Algorithm failed: {e}", exc_info=True)
        results['genetic_algorithm'] = {'success': False, 'error': str(e)}
    
    # Boruta
    logger.info("\n" + "="*70)
    logger.info("METHOD 3/3: Boruta")
    logger.info("="*70)
    try:
        start = time.time()
        boruta_indices, boruta_meta = boruta_feature_selection(X, y, top_k)
        elapsed = time.time() - start
        
        results['boruta'] = {
            'indices': boruta_indices,
            'num_features': len(boruta_indices),
            'time': elapsed,
            **boruta_meta
        }
    except Exception as e:
        logger.error(f"Boruta failed: {e}", exc_info=True)
        results['boruta'] = {'success': False, 'error': str(e)}
    
    return results
