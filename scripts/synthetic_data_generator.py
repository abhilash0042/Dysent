"""
Synthetic Benign Traffic Generator
Generates realistic synthetic benign network traffic to balance the dataset
Uses statistical modeling based on real benign samples
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import logging
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import FeatureExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SyntheticGenerator")

class SyntheticBenignGenerator:
    """Generate synthetic benign traffic using statistical modeling"""
    
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.gmm = None
        self.feature_names = None
        self.benign_stats = None
        
    def fit(self, benign_features):
        """
        Learn distribution from real benign samples
        
        Args:
            benign_features: numpy array of benign traffic features (N, features)
        """
        logger.info(f"Learning distribution from {len(benign_features)} benign samples...")
        
        # Fit scaler
        self.scaler.fit(benign_features)
        X_scaled = self.scaler.transform(benign_features)
        
        # Convert to float64 for numerical stability
        X_scaled = X_scaled.astype(np.float64)
        
        # Fit Gaussian Mixture Model (captures complex distributions)
        n_components = min(3, len(benign_features) // 200)  # Fewer components for stability
        n_components = max(1, n_components)  # At least 1 component
        
        logger.info(f"Fitting Gaussian Mixture Model with {n_components} components...")
        
        self.gmm = GaussianMixture(
            n_components=n_components,
            covariance_type='diag',  # Diagonal instead of full for stability
            random_state=self.random_state,
            max_iter=100,
            reg_covar=1e-4,  # Regularization for numerical stability
            n_init=3
        )
        self.gmm.fit(X_scaled)
        
        # Store statistics for validation
        self.benign_stats = {
            'mean': np.mean(benign_features, axis=0),
            'std': np.std(benign_features, axis=0),
            'min': np.min(benign_features, axis=0),
            'max': np.max(benign_features, axis=0)
        }
        
        logger.info("✅ Model fitted successfully")
        
    def generate(self, n_samples):
        """
        Generate synthetic benign samples
        
        Args:
            n_samples: Number of synthetic samples to generate
            
        Returns:
            numpy array of synthetic features (n_samples, features)
        """
        if self.gmm is None:
            raise ValueError("Generator not fitted! Call fit() first.")
        
        logger.info(f"Generating {n_samples} synthetic benign samples...")
        
        # Sample from GMM
        X_synthetic_scaled, _ = self.gmm.sample(n_samples)
        
        # Inverse transform to original scale
        X_synthetic = self.scaler.inverse_transform(X_synthetic_scaled)
        
        # Clip to realistic bounds (based on real data statistics)
        X_synthetic = np.clip(
            X_synthetic,
            self.benign_stats['min'],
            self.benign_stats['max']
        )
        
        logger.info("✅ Synthetic samples generated")
        
        return X_synthetic
    
    def validate_quality(self, synthetic_samples, real_samples):
        """
        Validate synthetic data quality using statistical tests
        
        Args:
            synthetic_samples: Generated synthetic samples
            real_samples: Original real benign samples
        """
        logger.info("\n" + "="*70)
        logger.info("📊 SYNTHETIC DATA QUALITY VALIDATION")
        logger.info("="*70)
        
        # Compare distributions
        logger.info("\nStatistical Comparison:")
        logger.info("-"*70)
        
        for i in range(min(5, synthetic_samples.shape[1])):  # Check first 5 features
            real_mean = np.mean(real_samples[:, i])
            real_std = np.std(real_samples[:, i])
            
            synth_mean = np.mean(synthetic_samples[:, i])
            synth_std = np.std(synthetic_samples[:, i])
            
            mean_diff = abs(real_mean - synth_mean) / (real_mean + 1e-8) * 100
            std_diff = abs(real_std - synth_std) / (real_std + 1e-8) * 100
            
            logger.info(f"\nFeature {i}:")
            logger.info(f"  Real - Mean: {real_mean:.4f}, Std: {real_std:.4f}")
            logger.info(f"  Synth - Mean: {synth_mean:.4f}, Std: {synth_std:.4f}")
            logger.info(f"  Difference - Mean: {mean_diff:.2f}%, Std: {std_diff:.2f}%")
        
        logger.info("\n" + "="*70 + "\n")


def generate_balanced_dataset(dataset_path, target_benign_ratio=0.5, output_path=None):
    """
    Create a balanced dataset by adding synthetic benign samples
    
    Args:
        dataset_path: Path to original imbalanced dataset
        target_benign_ratio: Desired ratio of benign samples (0.5 = 50/50)
        output_path: Where to save the balanced dataset (optional)
    
    Returns:
        X, y arrays of balanced dataset
    """
    logger.info("="*70)
    logger.info("🎯 BALANCED DATASET GENERATION")
    logger.info("="*70)
    
    # Load original dataset
    logger.info(f"\n📂 Loading dataset from: {dataset_path.name}")
    df = pd.read_csv(dataset_path, nrows=50000, encoding='utf-8', low_memory=False)
    logger.info(f"Loaded: {len(df):,} samples")
    
    # Preprocess
    logger.info("🔄 Preprocessing...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # Split by class
    benign_mask = (y == 0)
    attack_mask = ~benign_mask
    
    X_benign = X[benign_mask]
    X_attack = X[attack_mask]
    
    n_benign = len(X_benign)
    n_attack = len(X_attack)
    
    logger.info(f"\nOriginal Distribution:")
    logger.info(f"  Benign: {n_benign:,} ({n_benign/(n_benign+n_attack)*100:.2f}%)")
    logger.info(f"  Attack: {n_attack:,} ({n_attack/(n_benign+n_attack)*100:.2f}%)")
    
    # Calculate needed synthetic samples
    total_desired = n_benign + n_attack
    desired_benign = int(total_desired * target_benign_ratio)
    n_synthetic_needed = desired_benign - n_benign
    
    if n_synthetic_needed <= 0:
        logger.info("\n✅ Dataset already balanced!")
        return X, y
    
    logger.info(f"\n🎲 Generating {n_synthetic_needed:,} synthetic benign samples...")
    
    # Generate synthetic data
    generator = SyntheticBenignGenerator(random_state=42)
    generator.fit(X_benign)
    
    X_synthetic = generator.generate(n_synthetic_needed)
    
    # Validate quality
    generator.validate_quality(X_synthetic, X_benign)
    
    # Combine datasets
    X_benign_combined = np.vstack([X_benign, X_synthetic])
    y_benign_combined = np.zeros(len(X_benign_combined))
    
    X_balanced = np.vstack([X_benign_combined, X_attack])
    y_balanced = np.concatenate([y_benign_combined, y[attack_mask]])
    
    # Shuffle
    indices = np.random.RandomState(42).permutation(len(X_balanced))
    X_balanced = X_balanced[indices]
    y_balanced = y_balanced[indices]
    
    logger.info("\n" + "="*70)
    logger.info("✅ BALANCED DATASET CREATED")
    logger.info("="*70)
    logger.info(f"\nFinal Distribution:")
    logger.info(f"  Benign: {len(X_benign_combined):,} ({len(X_benign_combined)/len(X_balanced)*100:.2f}%)")
    logger.info(f"    - Real: {n_benign:,}")
    logger.info(f"    - Synthetic: {n_synthetic_needed:,}")
    logger.info(f"  Attack: {n_attack:,} ({n_attack/len(X_balanced)*100:.2f}%)")
    logger.info(f"  Total: {len(X_balanced):,}")
    logger.info("="*70 + "\n")
    
    return X_balanced, y_balanced


if __name__ == "__main__":
    # Example usage
    DATASET_PATH = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset\cicddos2019_dataset.csv")
    
    X_balanced, y_balanced = generate_balanced_dataset(
        DATASET_PATH,
        target_benign_ratio=0.5  # 50/50 balance
    )
    
    logger.info("✅ Ready for training!")
