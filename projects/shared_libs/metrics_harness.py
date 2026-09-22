"""Research evaluation metrics and reproducible result helpers."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import (
    precision_score, recall_score, f1_score, average_precision_score,
    confusion_matrix, matthews_corrcoef, balanced_accuracy_score,
)


def binary_metrics(y_true, y_pred, y_score=None):
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out = {
        'precision': float(precision_score(y_true, y_pred, zero_division=0)),
        'recall': float(recall_score(y_true, y_pred, zero_division=0)),
        'f1': float(f1_score(y_true, y_pred, zero_division=0)),
        'fpr': float(fp / max(fp + tn, 1)),
        'mcc': float(matthews_corrcoef(y_true, y_pred)) if len(np.unique(y_true)) > 1 else 0.0,
        'balanced_accuracy': float(balanced_accuracy_score(y_true, y_pred)),
        'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp),
    }
    if y_score is not None and len(np.unique(y_true)) > 1:
        out['pr_auc'] = float(average_precision_score(y_true, np.asarray(y_score)))
    else:
        out['pr_auc'] = 0.0
    return out


def save_json(path: str | Path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
