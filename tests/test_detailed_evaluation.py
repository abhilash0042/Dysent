"""
Comprehensive Model Evaluation with Class Imbalance Metrics
Calculates Precision, Recall, F1, Balanced Accuracy, Confusion Matrix
"""

import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix, classification_report, 
    balanced_accuracy_score, roc_auc_score,
    precision_recall_fscore_support
)

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import FeatureExtractor, split_data
from tensorflow import keras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DetailedEval")

# Paths
DATASET_PATH = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset\cicddos2019_dataset.csv")
MODEL_PATH = Path(r"c:\Users\HP\Desktop\Major Project\Main File-Code\ddosdfl\models\best_model.keras")

def comprehensive_evaluation():
    logger.info("="*70)
    logger.info("🔍 COMPREHENSIVE MODEL EVALUATION (Imbalance-Aware)")
    logger.info("="*70)
    
    # 1. Load Dataset
    logger.info("\n📂 Loading dataset...")
    df = pd.read_csv(DATASET_PATH, nrows=50000, encoding='utf-8', low_memory=False)
    logger.info(f"Loaded: {len(df):,} samples")
    
    # 2. Preprocess
    logger.info("🔄 Preprocessing...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # Reshape
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    
    # 3. Split (using same ratio as training)
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X, y, train_ratio=0.7, val_ratio=0.1, test_ratio=0.2
    )
    
    logger.info(f"Test set size: {len(X_test):,}")
    
    # Check test set distribution
    unique, counts = np.unique(y_test, return_counts=True)
    logger.info("\nTest Set Distribution:")
    for cls, count in zip(unique, counts):
        pct = count / len(y_test) * 100
        label = "Benign" if cls == 0 else "Attack"
        logger.info(f"  {label} (Class {cls}): {count:,} ({pct:.2f}%)")
    
    # 4. Load Model
    logger.info(f"\n🧠 Loading model from: {MODEL_PATH.name}")
    
    if not MODEL_PATH.exists():
        logger.error(f"❌ Model not found: {MODEL_PATH}")
        return
    
    model = keras.models.load_model(MODEL_PATH)
    
    # 5. Predict
    logger.info("🎯 Making predictions...")
    y_pred_proba = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_pred_proba, axis=1)
    
    # 6. Calculate Metrics
    logger.info("\n" + "="*70)
    logger.info("📊 EVALUATION RESULTS")
    logger.info("="*70)
    
    # Standard Accuracy
    accuracy = np.mean(y_pred == y_test)
    logger.info(f"\n✅ Standard Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Balanced Accuracy (accounts for imbalance)
    balanced_acc = balanced_accuracy_score(y_test, y_pred)
    logger.info(f"✅ Balanced Accuracy: {balanced_acc:.4f} ({balanced_acc*100:.2f}%)")
    
    # Per-class metrics
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, average=None, zero_division=0
    )
    
    logger.info("\n" + "-"*70)
    logger.info("PER-CLASS METRICS:")
    logger.info("-"*70)
    
    class_names = ["Benign", "Attack"]
    for i, name in enumerate(class_names):
        logger.info(f"\n{name} (Class {i}):")
        logger.info(f"  Precision: {precision[i]:.4f} ({precision[i]*100:.2f}%)")
        logger.info(f"  Recall:    {recall[i]:.4f} ({recall[i]*100:.2f}%)")
        logger.info(f"  F1-Score:  {f1[i]:.4f}")
        logger.info(f"  Support:   {support[i]:,} samples")
    
    # Macro averages (equal weight per class)
    macro_precision = np.mean(precision)
    macro_recall = np.mean(recall)
    macro_f1 = np.mean(f1)
    
    logger.info("\n" + "-"*70)
    logger.info("MACRO AVERAGES (Equal Weight per Class):")
    logger.info("-"*70)
    logger.info(f"  Precision: {macro_precision:.4f}")
    logger.info(f"  Recall:    {macro_recall:.4f}")
    logger.info(f"  F1-Score:  {macro_f1:.4f}")
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    
    logger.info("\n" + "-"*70)
    logger.info("CONFUSION MATRIX:")
    logger.info("-"*70)
    logger.info("\n                Predicted")
    logger.info("              Benign  Attack")
    logger.info(f"Actual Benign  {cm[0][0]:6d}  {cm[0][1]:6d}")
    logger.info(f"       Attack  {cm[1][0]:6d}  {cm[1][1]:6d}")
    
    # Detailed confusion matrix analysis
    tn, fp, fn, tp = cm.ravel()
    
    logger.info("\n" + "-"*70)
    logger.info("CONFUSION MATRIX BREAKDOWN:")
    logger.info("-"*70)
    logger.info(f"  True Negatives (TN):  {tn:,} - Correctly identified as Benign")
    logger.info(f"  False Positives (FP): {fp:,} - Benign flagged as Attack")
    logger.info(f"  False Negatives (FN): {fn:,} - Attack missed (flagged as Benign) ⚠️")
    logger.info(f"  True Positives (TP):  {tp:,} - Correctly identified as Attack")
    
    # ROC-AUC (if binary classification)
    if len(np.unique(y_test)) == 2:
        try:
            auc = roc_auc_score(y_test, y_pred_proba[:, 1])
            logger.info(f"\n✅ ROC-AUC Score: {auc:.4f}")
        except:
            pass
    
    # Final Verdict
    logger.info("\n" + "="*70)
    logger.info("🎯 VERDICT:")
    logger.info("="*70)
    
    if balanced_acc >= 0.95:
        logger.info("✅ EXCELLENT: Balanced accuracy ≥ 95%")
        logger.info("   The model performs well on BOTH classes despite imbalance.")
    elif balanced_acc >= 0.90:
        logger.info("✅ GOOD: Balanced accuracy ≥ 90%")
        logger.info("   Solid performance across classes.")
    elif balanced_acc >= 0.80:
        logger.info("⚠️  ACCEPTABLE: Balanced accuracy ≥ 80%")
        logger.info("   Some room for improvement on minority class.")
    else:
        logger.info("❌ POOR: Balanced accuracy < 80%")
        logger.info("   May be biased toward majority class.")
    
    # Check if model is just predicting majority class
    attack_prediction_rate = np.sum(y_pred == 1) / len(y_pred)
    logger.info(f"\nModel predicts 'Attack' for: {attack_prediction_rate*100:.2f}% of samples")
    
    if attack_prediction_rate > 0.95:
        logger.warning("⚠️  WARNING: Model may be over-predicting Attack class")
    elif attack_prediction_rate < 0.05:
        logger.warning("⚠️  WARNING: Model may be over-predicting Benign class")
    else:
        logger.info("✅ Model makes balanced predictions")
    
    logger.info("\n" + "="*70)
    logger.info("✅ EVALUATION COMPLETE")
    logger.info("="*70 + "\n")

if __name__ == "__main__":
    comprehensive_evaluation()
