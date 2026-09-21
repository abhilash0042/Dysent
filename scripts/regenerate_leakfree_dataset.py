"""
Regenerate the CICDDoS2019 processed arrays without leaked label columns.

The original pipeline let two non-features into X:
  index 0  'Unnamed: 0'  - saved CSV row number; the files are grouped by attack
                            type, so the row number correlates with the class
  index 78 'Class'       - the binary Benign/Attack ground truth

Both were picked up by feature selection and ended up among the 40 model inputs,
which is why the reported accuracy was ~98% and why it collapses when those
columns are unavailable (as they always are at inference time).

This script drops them, re-runs the same ensemble selection over the remaining
77 columns, and writes a matching scaler so live inference can normalize input
exactly the way training did.

Usage:
    python scripts/regenerate_leakfree_dataset.py
"""

import sys
import pickle
import logging
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from sklearn.preprocessing import StandardScaler

from projects.shared_libs.feature_selection import FeatureSelector

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

PROCESSED = project_root / 'data' / 'processed'
SRC_DATA = PROCESSED / 'cicddos2019_full_processed.npz'
SRC_EXTRACTOR = PROCESSED / 'cicddos2019_full_feature_extractor.pkl'

OUT_DATA = PROCESSED / 'cicddos2019_leakfree_processed.npz'
OUT_EXTRACTOR = PROCESSED / 'cicddos2019_leakfree_feature_extractor.pkl'
OUT_SELECTION = PROCESSED / 'cicddos2019_leakfree_feature_selection.pkl'

LEAKY_NAMES = {'Class'}
TOP_K = 40
SELECTION_SAMPLE = 120_000  # mutual_info over 431k x 77 is needlessly slow


def is_leaky(name: str) -> bool:
    return name in LEAKY_NAMES or name.startswith('Unnamed:')


def subset_scaler(scaler: StandardScaler, keep: list) -> StandardScaler:
    """Restrict a fitted StandardScaler to a column subset, preserving its statistics."""
    out = StandardScaler()
    out.mean_ = scaler.mean_[keep].copy()
    out.scale_ = scaler.scale_[keep].copy()
    out.var_ = scaler.var_[keep].copy()
    out.n_features_in_ = len(keep)
    out.n_samples_seen_ = scaler.n_samples_seen_
    return out


def main():
    logger.info("Loading source arrays...")
    data = np.load(SRC_DATA, allow_pickle=True)
    X, y = data['X'], data['y']

    with open(SRC_EXTRACTOR, 'rb') as f:
        extractor = pickle.load(f)
    names = list(extractor['feature_names'])

    if X.shape[1] != len(names):
        raise ValueError(f"X has {X.shape[1]} columns but extractor lists {len(names)} names")

    leaky = [i for i, n in enumerate(names) if is_leaky(n)]
    keep = [i for i in range(len(names)) if i not in leaky]
    clean_names = [names[i] for i in keep]

    logger.info(f"Source: {X.shape[0]:,} rows x {X.shape[1]} columns")
    logger.info(f"Removing {len(leaky)} leaked columns: {[names[i] for i in leaky]}")
    logger.info(f"Remaining: {len(keep)} legitimate features")

    X_clean = X[:, keep]

    logger.info(f"Re-running ensemble selection (top {TOP_K}) on the clean columns...")
    rng = np.random.default_rng(42)
    sample = rng.choice(len(X_clean), min(SELECTION_SAMPLE, len(X_clean)), replace=False)

    selector = FeatureSelector()
    _, selected = selector.ensemble_selection(
        X_clean[sample], y[sample], top_k=TOP_K, feature_names=clean_names
    )
    selected = [int(i) for i in selected]

    logger.info("Selected features, in the order the model will receive them:")
    for pos, idx in enumerate(selected):
        logger.info(f"  [{pos:2d}] {clean_names[idx]}")

    logger.info("Writing outputs...")
    np.savez_compressed(OUT_DATA, X=X_clean, y=y)

    with open(OUT_EXTRACTOR, 'wb') as f:
        pickle.dump({
            'scaler': subset_scaler(extractor['scaler'], keep),
            'label_encoder': extractor['label_encoder'],
            'categorical_encoders': extractor['categorical_encoders'],
            'feature_names': clean_names,
            'removed_leaky_columns': [names[i] for i in leaky],
        }, f)

    with open(OUT_SELECTION, 'wb') as f:
        pickle.dump({
            'ensemble': {
                'indices': selected,
                'names': [clean_names[i] for i in selected],
                'num_features': len(selected),
                'success': True,
            }
        }, f)

    logger.info(f"  {OUT_DATA.name}      {X_clean.shape}")
    logger.info(f"  {OUT_EXTRACTOR.name}")
    logger.info(f"  {OUT_SELECTION.name}")
    logger.info("Done. No column in these outputs derives from the label.")


if __name__ == '__main__':
    main()
