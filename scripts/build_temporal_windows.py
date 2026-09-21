"""
Build Path-B temporal windows from the downloaded CICDDoS2019 CSV subset.

Guarantees (no silent mismatch):
  1. Every selected feature maps through cicddos_column_contract.CSV_TO_CONTRACT
  2. Labels map through LABEL_TO_CONTRACT into the EXISTING leak-free LabelEncoder
  3. Leaky columns (Unnamed: 0, Class, Label) never enter X
  4. Existing processed/*.npz artifacts are never overwritten

Output:
  data/processed/cicddos2019_temporal_windows.npz
    X: (N, timesteps, n_features) float32
    y: (N,) int64   -- same class indices as leak-free model
    feature_names: length n_features
    class_names: from the leak-free label encoder
    meta: source files, window params

Usage:
  python scripts/build_temporal_windows.py
  python scripts/build_temporal_windows.py --timesteps 10 --max-per-file 50000
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts'))

from cicddos_column_contract import (  # noqa: E402
    LABEL_TO_CONTRACT,
    LEAKY_COLUMNS,
    PATHB_KEY_COLUMNS,
    normalize_columns,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

RAW_DIR = project_root / 'data' / 'raw' / 'cicddos2019_subset'
OUT_NPZ = project_root / 'data' / 'processed' / 'cicddos2019_temporal_windows.npz'
OUT_META = project_root / 'data' / 'processed' / 'cicddos2019_temporal_windows_meta.json'
SELECTION_PKL = project_root / 'data' / 'processed' / 'cicddos2019_leakfree_feature_selection.pkl'
EXTRACTOR_PKL = project_root / 'data' / 'processed' / 'cicddos2019_leakfree_feature_extractor.pkl'


def load_contract():
    with open(SELECTION_PKL, 'rb') as f:
        selected = list(pickle.load(f)['ensemble']['names'])
    with open(EXTRACTOR_PKL, 'rb') as f:
        ext = pickle.load(f)
    class_names = list(ext['label_encoder'].classes_)
    scaler = ext['scaler']
    all_clean = list(ext['feature_names'])
    return selected, class_names, scaler, all_clean, ext['label_encoder']


def load_and_normalize(csv_path: Path, selected: list[str]) -> pd.DataFrame:
    df = pd.read_csv(csv_path, low_memory=False)
    mapping = normalize_columns(df.columns)
    df = df.rename(columns=mapping)

    # CICFlowMeter dumps 'Fwd Header Length' twice (second as *.1). Keep first only.
    if df.columns.duplicated().any():
        dups = df.columns[df.columns.duplicated()].unique().tolist()
        logger.info(f"  dropping duplicate columns after rename: {dups}")
        df = df.loc[:, ~df.columns.duplicated()]

    required = set(selected) | {'Timestamp', 'Source IP', 'Label'}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"{csv_path.name}: missing required columns after rename: {missing}\n"
            f"  Have: {sorted(df.columns)[:30]}..."
        )

    # Drop anything leaky that somehow survived rename
    drop = [c for c in df.columns if c in LEAKY_COLUMNS and c != 'Label']
    if drop:
        logger.info(f"  dropping leaky columns: {drop}")
        df = df.drop(columns=drop)

    # Normalize labels to contract names
    df['Label'] = df['Label'].astype(str).str.strip().map(
        lambda x: LABEL_TO_CONTRACT.get(x, x)
    )
    unknown = sorted(set(df['Label']) - set(LABEL_TO_CONTRACT.values()))
    if unknown:
        logger.warning(f"  unknown labels (will be dropped): {unknown}")
        df = df[df['Label'].isin(LABEL_TO_CONTRACT.values())]

    df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df = df.dropna(subset=['Timestamp', 'Source IP'])
    return df


def scale_selected(df: pd.DataFrame, selected: list[str], scaler, all_clean: list[str]) -> np.ndarray:
    """
    Apply the EXISTING leak-free StandardScaler to the selected columns.

    The scaler was fitted on all 77 clean columns. We reconstruct a 77-wide
    matrix (zeros for unused cols), transform, then slice selected indices.
    That keeps live/inference scaling identical to training.
    """
    # Build 77-wide frame in clean-feature order
    wide = np.zeros((len(df), len(all_clean)), dtype=np.float64)
    present = []
    for i, name in enumerate(all_clean):
        if name in df.columns:
            col = pd.to_numeric(df[name], errors='coerce').fillna(0.0).to_numpy()
            col = np.nan_to_num(col, nan=0.0, posinf=0.0, neginf=0.0)
            wide[:, i] = col
            present.append(name)

    scaled = scaler.transform(wide)
    sel_idx = [all_clean.index(n) for n in selected]
    return scaled[:, sel_idx].astype(np.float32)


def aggregate_one_second(
    df: pd.DataFrame,
    X_scaled: np.ndarray,
    y: np.ndarray,
    selected: list[str],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Collapse flows into 1-second buckets per Source IP.

    Each bucket is the mean of scaled features in that second. Label is the
    majority class in the second (ties keep the last flow's label).
    """
    ts = pd.to_datetime(df['Timestamp']).dt.floor('s')
    src = df['Source IP'].astype(str).to_numpy()
    work = pd.DataFrame({
        'Source IP': src,
        'second': ts.to_numpy(),
        'y': y,
    })
    feat = pd.DataFrame(X_scaled, columns=selected)
    work = pd.concat([work.reset_index(drop=True), feat.reset_index(drop=True)], axis=1)

    grouped = work.groupby(['Source IP', 'second'], sort=True)
    X_agg = grouped[selected].mean().to_numpy(dtype=np.float32)

    def majority(series: pd.Series) -> int:
        vals, counts = np.unique(series.to_numpy(), return_counts=True)
        return int(vals[counts.argmax()])

    y_agg = grouped['y'].agg(majority).to_numpy(dtype=np.int64)
    keys = grouped.size().reset_index()[['Source IP', 'second']]
    logger.info(f"  1s buckets: {len(keys):,} from {len(df):,} flows")
    return keys, X_agg, y_agg


def build_windows(
    keys: pd.DataFrame,
    X_scaled: np.ndarray,
    y: np.ndarray,
    timesteps: int,
    benign_idx: int,
    pad_benign_min: int = 3,
    stride: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Stack `timesteps` time-sorted 1-second buckets per Source IP.

    Attack sources: non-overlapping windows of exactly `timesteps` buckets.
    Benign sources: if they have at least `pad_benign_min` buckets, pad the
    last observation out to `timesteps` so sparse background traffic still
    forms a sequence (this is what 51-window collapse was killing).
    """
    windows_x, windows_y, windows_src = [], [], []
    src = keys['Source IP'].to_numpy()

    i = 0
    n = len(keys)
    while i < n:
        j = i
        while j < n and src[j] == src[i]:
            j += 1
        length = j - i
        Xo = X_scaled[i:j]
        yo = y[i:j]
        is_benign_source = (yo == benign_idx).mean() >= 0.5

        if length >= timesteps:
            for start in range(0, length - timesteps + 1, stride):
                chunk = Xo[start:start + timesteps]
                labels = yo[start:start + timesteps]
                vals, counts = np.unique(labels, return_counts=True)
                windows_x.append(chunk)
                windows_y.append(vals[counts.argmax()])
                windows_src.append(src[i])
        elif is_benign_source and length >= pad_benign_min:
            pad = timesteps - length
            chunk = np.concatenate([Xo, np.repeat(Xo[-1:], pad, axis=0)], axis=0)
            windows_x.append(chunk)
            windows_y.append(benign_idx)
            windows_src.append(src[i])
        i = j

    if not windows_x:
        return (
            np.empty((0, timesteps, X_scaled.shape[1]), dtype=np.float32),
            np.empty((0,), dtype=np.int64),
            np.empty((0,), dtype=object),
        )
    return (
        np.stack(windows_x).astype(np.float32),
        np.asarray(windows_y, dtype=np.int64),
        np.asarray(windows_src, dtype=object),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timesteps', type=int, default=10)
    parser.add_argument('--max-attack-per-file', type=int, default=40000,
                        help='Cap ATTACK rows per CSV. All BENIGN rows are kept.')
    parser.add_argument('--stride', type=int, default=1,
                        help='Window stride in seconds. 1 = overlapping (more training samples)')
    parser.add_argument('--pad-benign-min', type=int, default=3,
                        help='Pad benign sources with this many 1s buckets up to timesteps')
    args = parser.parse_args()

    selected, class_names, scaler, all_clean, label_encoder = load_contract()
    class_to_idx = {c: i for i, c in enumerate(class_names)}
    benign_idx = class_to_idx['Benign']
    logger.info(f"Contract: {len(selected)} features, {len(class_names)} classes, timesteps={args.timesteps}")

    csv_files = sorted(RAW_DIR.glob('*.csv'))
    if not csv_files:
        raise FileNotFoundError(f"No CSVs in {RAW_DIR}. Run the download first.")

    all_X, all_y, all_src = [], [], []
    per_file = {}

    for csv_path in csv_files:
        logger.info(f"Processing {csv_path.name}...")
        df = load_and_normalize(csv_path, selected)

        # Never downsample BENIGN. Cap only attack rows so we don't starve the
        # minority class the way a random sample of 30k did.
        is_benign = df['Label'].eq('Benign')
        if args.max_attack_per_file and (~is_benign).sum() > args.max_attack_per_file:
            attack = df.loc[~is_benign].sample(args.max_attack_per_file, random_state=42)
            df = pd.concat([df.loc[is_benign], attack], ignore_index=True)
            logger.info(f"  kept {int(is_benign.sum()):,} BENIGN + {args.max_attack_per_file:,} attack rows")
        else:
            logger.info(f"  rows={len(df):,}  BENIGN={int(is_benign.sum()):,}")

        missing = [n for n in selected if n not in df.columns]
        if missing:
            raise RuntimeError(f"{csv_path.name}: selected features still missing: {missing}")

        mapped = df['Label'].map(class_to_idx)
        keep = mapped.notna()
        dropped = int((~keep).sum())
        if dropped:
            logger.warning(f"  dropping {dropped} rows with labels outside contract")
        df = df.loc[keep].copy()
        y = mapped.loc[keep].astype(np.int64).to_numpy()

        X_scaled = scale_selected(df, selected, scaler, all_clean)
        df = df.reset_index(drop=True)
        keys, X_agg, y_agg = aggregate_one_second(df, X_scaled, y, selected)
        Xw, yw, sw = build_windows(
            keys, X_agg, y_agg, args.timesteps, benign_idx, args.pad_benign_min, args.stride
        )
        logger.info(f"  -> {len(Xw):,} windows  labels={dict(zip(*np.unique(yw, return_counts=True))) if len(yw) else {}}")
        per_file[csv_path.name] = {
            'rows': int(len(df)),
            'benign_rows': int((df['Label'] == 'Benign').sum()),
            'windows': int(len(Xw)),
            'label_counts': {class_names[int(k)]: int(v) for k, v in zip(*np.unique(yw, return_counts=True))} if len(yw) else {},
        }
        if len(Xw):
            all_X.append(Xw)
            all_y.append(yw)
            all_src.append(sw)

    if not all_X:
        raise RuntimeError("No temporal windows produced. Check Source IP diversity / timesteps.")

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y, axis=0)
    sources = np.concatenate(all_src, axis=0)
    logger.info(f"TOTAL windows: {X.shape}  y={y.shape}")

    # Final safety checks
    assert X.shape[1] == args.timesteps, X.shape
    assert X.shape[2] == len(selected), (X.shape, len(selected))
    assert not np.isnan(X).any(), "NaNs in X"
    assert set(np.unique(y)).issubset(set(range(len(class_names))))

    OUT_NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT_NPZ,
        X=X,
        y=y,
        source_ip=sources.astype(object),
        feature_names=np.array(selected, dtype=object),
        class_names=np.array(class_names, dtype=object),
        timesteps=np.array(args.timesteps),
    )
    meta = {
        'output': str(OUT_NPZ),
        'shape': list(X.shape),
        'timesteps': args.timesteps,
        'stride': args.stride,
        'n_features': len(selected),
        'feature_names': selected,
        'class_names': class_names,
        'per_file': per_file,
        'notes': [
            'Windows are 10 x 1-second buckets per Source IP, not 10 consecutive raw flows',
            'Scaled with cicddos2019_leakfree_feature_extractor.pkl StandardScaler',
            'Labels encoded with the same LabelEncoder as the leak-free model',
            'Leaky columns Unnamed:0 / Class never entered X',
            'All BENIGN rows are kept; only attack rows are capped per file',
            'Short benign sources (>=3 seconds) are padded to 10 timesteps',
            'Does NOT overwrite cicddos2019_full_processed.npz or leakfree arrays',
        ],
    }
    OUT_META.write_text(json.dumps(meta, indent=2))
    logger.info(f"Wrote {OUT_NPZ}")
    logger.info(f"Wrote {OUT_META}")
    logger.info("Done — Path-B windows match the leak-free contract.")


if __name__ == '__main__':
    main()
