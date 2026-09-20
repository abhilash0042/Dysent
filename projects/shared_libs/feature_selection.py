"""
Advanced Feature Selection Module for DDoS Detection

Implements multiple feature selection strategies to reduce dimensionality
and improve model performance.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import (
    mutual_info_classif,
    SelectKBest,
    f_classif,
    chi2,
    RFE
)
from sklearn.decomposition import PCA
from typing import List, Tuple, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class FeatureSelector:
    """Advanced feature selection for DDoS detection"""
    
    def __init__(self):
        self.selected_features = None
        self.feature_scores = None
        self.selection_method = None
        
    def mutual_information_selection(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_k: int = 40,
        feature_names: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Select features using Mutual Information
        
        Measures dependency between features and target.
        Good for: capturing non-linear relationships
        
        Args:
            X: Features
            y: Labels
            top_k: Number of features to select
            feature_names: Optional feature names
            
        Returns:
            Tuple of (selected X, selected feature indices)
        """
        logger.info(f"Selecting top {top_k} features using Mutual Information...")
        
        # Compute mutual information scores
        mi_scores = mutual_info_classif(X, y, random_state=42)
        
        # Get top k feature indices
        top_indices = np.argsort(mi_scores)[-top_k:][::-1]
        
        # Store scores
        self.feature_scores = dict(zip(range(len(mi_scores)), mi_scores))
        self.selected_features = top_indices
        self.selection_method = "mutual_information"
        
        # Log top features
        logger.info(f"Top 10 features by Mutual Information:")
        for idx in top_indices[:10]:
            fname = feature_names[idx] if feature_names else f"Feature_{idx}"
            logger.info(f"  {fname}: {mi_scores[idx]:.4f}")
        
        return X[:, top_indices], top_indices.tolist()
    
    def correlation_based_selection(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_k: int = 40,
        feature_names: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Select features using ANOVA F-statistic (correlation)
        
        Measures linear correlation between features and target.
        Good for: fast selection, interpretable scores
        
        Args:
            X: Features
            y: Labels
            top_k: Number of features to select
            feature_names: Optional feature names
            
        Returns:
            Tuple of (selected X, selected feature indices)
        """
        logger.info(f"Selecting top {top_k} features using ANOVA F-test...")
        
        # Compute F-scores
        f_scores, _ = f_classif(X, y)
        
        # Handle NaN scores
        f_scores = np.nan_to_num(f_scores, nan=0.0)
        
        # Get top k feature indices
        top_indices = np.argsort(f_scores)[-top_k:][::-1]
        
        # Store scores
        self.feature_scores = dict(zip(range(len(f_scores)), f_scores))
        self.selected_features = top_indices
        self.selection_method = "anova_f"
        
        # Log top features
        logger.info(f"Top 10 features by F-score:")
        for idx in top_indices[:10]:
            fname = feature_names[idx] if feature_names else f"Feature_{idx}"
            logger.info(f"  {fname}: {f_scores[idx]:.2f}")
        
        return X[:, top_indices], top_indices.tolist()
    
    def random_forest_importance(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_k: int = 40,
        feature_names: Optional[List[str]] = None,
        n_estimators: int = 100
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Select features using Random Forest feature importance
        
        Trains RF and uses Gini importance.
        Good for: capturing feature interactions, robust selection
        
        Args:
            X: Features
            y: Labels
            top_k: Number of features to select
            feature_names: Optional feature names
            n_estimators: Number of RF trees
            
        Returns:
            Tuple of (selected X, selected feature indices)
        """
        logger.info(f"Selecting top {top_k} features using Random Forest importance...")
        logger.info(f"Training Random Forest with {n_estimators} estimators...")
        
        # Train Random Forest
        rf = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=42,
            n_jobs=-1,
            max_depth=10,
            max_samples=min(10000, len(X))  # Limit for speed
        )
        rf.fit(X, y)
        
        # Get feature importances
        importances = rf.feature_importances_
        
        # Get top k feature indices
        top_indices = np.argsort(importances)[-top_k:][::-1]
        
        # Store scores
        self.feature_scores = dict(zip(range(len(importances)), importances))
        self.selected_features = top_indices
        self.selection_method = "random_forest"
        
        # Log top features
        logger.info(f"Top 10 features by RF importance:")
        for idx in top_indices[:10]:
            fname = feature_names[idx] if feature_names else f"Feature_{idx}"
            logger.info(f"  {fname}: {importances[idx]:.4f}")
        
        return X[:, top_indices], top_indices.tolist()
    
    def recursive_feature_elimination(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_k: int = 40,
        feature_names: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Select features using Recursive Feature Elimination (RFE)
        
        Iteratively removes least important features.
        Good for: finding optimal feature subset, but slow
        
        Args:
            X: Features
            y: Labels
            top_k: Number of features to select
            feature_names: Optional feature names
            
        Returns:
            Tuple of (selected X, selected feature indices)
        """
        logger.info(f"Selecting top {top_k} features using RFE...")
        logger.info("This may take a few minutes...")
        
        # Use Random Forest as base estimator
        rf = RandomForestClassifier(
            n_estimators=50,
            random_state=42,
            n_jobs=-1,
            max_depth=10
        )
        
        # RFE
        rfe = RFE(
            estimator=rf,
            n_features_to_select=top_k,
            step=5  # Remove 5 features at a time
        )
        
        # Sample for speed if dataset is large
        if len(X) > 50000:
            sample_idx = np.random.choice(len(X), 50000, replace=False)
            X_sample, y_sample = X[sample_idx], y[sample_idx]
        else:
            X_sample, y_sample = X, y
        
        rfe.fit(X_sample, y_sample)
        
        # Get selected feature indices
        top_indices = np.where(rfe.support_)[0]
        
        # Store
        self.selected_features = top_indices
        self.selection_method = "rfe"
        
        # Log selected features
        logger.info(f"Selected {len(top_indices)} features via RFE:")
        for idx in top_indices[:10]:
            fname = feature_names[idx] if feature_names else f"Feature_{idx}"
            logger.info(f"  {fname}")
        
        return X[:, top_indices], top_indices.tolist()
    
    def variance_threshold_selection(
        self,
        X: np.ndarray,
        threshold: float = 0.01,
        feature_names: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Remove low-variance features
        
        Removes features with variance below threshold.
        Good for: removing constant/near-constant features
        
        Args:
            X: Features
            threshold: Variance threshold
            feature_names: Optional feature names
            
        Returns:
            Tuple of (selected X, selected feature indices)
        """
        logger.info(f"Removing features with variance < {threshold}...")
        
        # Compute variances
        variances = np.var(X, axis=0)
        
        # Select features above threshold
        selected_indices = np.where(variances >= threshold)[0]
        
        logger.info(f"Removed {len(variances) - len(selected_indices)} low-variance features")
        logger.info(f"Kept {len(selected_indices)} features")
        
        self.selected_features = selected_indices
        self.selection_method = "variance_threshold"
        
        return X[:, selected_indices], selected_indices.tolist()
    
    def pca_reduction(
        self,
        X: np.ndarray,
        n_components: int = 40,
        variance_explained: float = 0.95
    ) -> Tuple[np.ndarray, PCA]:
        """
        Dimensionality reduction using PCA
        
        Creates new orthogonal features via linear combinations.
        Good for: max variance retention, dimensionality reduction
        
        Args:
            X: Features
            n_components: Number of components (or None for variance_explained)
            variance_explained: Target variance to explain
            
        Returns:
            Tuple of (transformed X, fitted PCA)
        """
        logger.info(f"Applying PCA dimensionality reduction...")
        
        # Determine number of components
        if n_components:
            pca = PCA(n_components=n_components, random_state=42)
        else:
            pca = PCA(n_components=variance_explained, random_state=42)
        
        X_pca = pca.fit_transform(X)
        
        logger.info(f"Reduced to {pca.n_components_} components")
        logger.info(f"Variance explained: {pca.explained_variance_ratio_.sum():.4f}")
        logger.info(f"Top 5 components explain: {pca.explained_variance_ratio_[:5].sum():.4f}")
        
        self.selection_method = "pca"
        
        return X_pca, pca
    
    def ensemble_selection(
        self,
        X: np.ndarray,
        y: np.ndarray,
        top_k: int = 40,
        feature_names: Optional[List[str]] = None,
        methods: List[str] = ['mutual_info', 'anova_f', 'random_forest']
    ) -> Tuple[np.ndarray, List[int]]:
        """
        Ensemble feature selection (vote across multiple methods)
        
        Combines rankings from multiple methods.
        Good for: robust selection, consensus features
        
        Args:
            X: Features
            y: Labels
            top_k: Number of features to select
            feature_names: Optional feature names
            methods: Methods to use for voting
            
        Returns:
            Tuple of (selected X, selected feature indices)
        """
        logger.info(f"Ensemble feature selection using {methods}...")
        
        method_rankings = []
        
        # Get rankings from each method
        for method in methods:
            if method == 'mutual_info':
                scores = mutual_info_classif(X, y, random_state=42)
            elif method == 'anova_f':
                scores, _ = f_classif(X, y)
                scores = np.nan_to_num(scores, nan=0.0)
            elif method == 'random_forest':
                rf = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1, max_depth=10)
                rf.fit(X[:min(10000, len(X))], y[:min(10000, len(X))])
                scores = rf.feature_importances_
            
            # Rank features (higher score = lower rank number)
            ranks = np.argsort(np.argsort(scores)[::-1])
            method_rankings.append(ranks)
        
        # Average ranks
        avg_ranks = np.mean(method_rankings, axis=0)
        
        # Select top k by average rank
        top_indices = np.argsort(avg_ranks)[:top_k]
        
        logger.info(f"Selected {len(top_indices)} features by ensemble voting")
        
        self.selected_features = top_indices
        self.selection_method = "ensemble"
        
        return X[:, top_indices], top_indices.tolist()


def compare_selection_methods(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: Optional[List[str]] = None,
    top_k: int = 40
) -> Dict[str, List[int]]:
    """
    Compare different feature selection methods
    
    Args:
        X: Features
        y: Labels
        feature_names: Optional feature names
        top_k: Number of features to select
        
    Returns:
        Dictionary mapping method name to selected feature indices
    """
    logger.info("="*70)
    logger.info(f"Comparing Feature Selection Methods (top {top_k} features)")
    logger.info("="*70)
    
    selector = FeatureSelector()
    results = {}
    
    # 1. Mutual Information
    logger.info("\n" + "-"*70)
    _, mi_indices = selector.mutual_information_selection(X, y, top_k, feature_names)
    results['mutual_information'] = mi_indices
    
    # 2. ANOVA F-test
    logger.info("\n" + "-"*70)
    _, anova_indices = selector.correlation_based_selection(X, y, top_k, feature_names)
    results['anova_f'] = anova_indices
    
    # 3. Random Forest
    logger.info("\n" + "-"*70)
    _, rf_indices = selector.random_forest_importance(X, y, top_k, feature_names)
    results['random_forest'] = rf_indices
    
    # 4. Ensemble
    logger.info("\n" + "-"*70)
    _, ensemble_indices = selector.ensemble_selection(X, y, top_k, feature_names)
    results['ensemble'] = ensemble_indices
    
    # Analysis: Feature overlap
    logger.info("\n" + "="*70)
    logger.info("Feature Selection Overlap Analysis")
    logger.info("="*70)
    
    all_methods = ['mutual_information', 'anova_f', 'random_forest', 'ensemble']
    
    # Features selected by all methods
    common_features = set(results[all_methods[0]])
    for method in all_methods[1:]:
        common_features &= set(results[method])
    
    logger.info(f"Features selected by ALL methods ({len(common_features)}): {sorted(common_features)[:10]}...")
    
    # Features unique to each method
    for method in all_methods:
        unique = set(results[method])
        for other_method in all_methods:
            if other_method != method:
                unique -= set(results[other_method])
        logger.info(f"{method} unique features: {len(unique)}")
    
    return results
