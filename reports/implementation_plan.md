# Implementation Plan: Smart-Adaptive 2027 Dataset

## Goal

Create a new synthetic dataset representing "Smart-Adaptive 2027" attacks—highly evasive, AI-driven threats designed to bypass traditional and even some advanced filters. Test the FL-DDoS system's accuracy against this new threat landscape.

## 1. New Data Generator

**File:** `ddosdfl/scripts/data/generate_adaptive_2027_attacks.py`

**Attack Class Characteristics:**

1.  **Smart Pulse DDoS**: Short, high-intensity bursts synchronized to bypass rate limits (Sinusoidal triggers).
2.  **AI-Morphing Botnet**: Features (packet size, interval) that drift over time to evade static signatures.
3.  **Low-Rate DoS (LDoS)**: constant low-bandwidth attacks targeting specific application resources (hard to distinguish from normal flows).
4.  **Encrypted Tunnel Flood**: Mimics high-entropy TLS traffic (randomized payloads).

**Technical Specs:**

- **Features**: 40 (Standard CICFlowMeter format compatibility).
- **Samples**: 15,000 (Balanced/Imbalanced options).
- **Hardness**: High (Overlapping feature distributions with Benign).

## 2. Validation Test Script

**File:** `ddosdfl/tests/test_adaptive_2027_validation.py`

**Workflow:**

1.  **Generate** the new 2027 dataset.
2.  **Preprocess** (Reshape for CNN-BiLSTM).
3.  **Load** the existing pre-trained "Historical" model (simulated training on CICDDoS2019).
4.  **Apply Adaptive Transfer Learning**:
    - Detect similarity (Expect Low -> Discriminative Strategy).
    - Train/Fine-tune.
5.  **Evaluate & Report**:
    - Accuracy, Precision, Recall, F1.
    - Training Time.
    - Confusion Matrix (Text-based).

## 3. Execution & Reporting

- Run the test.
- Output the final accuracy to the user.
- Verify robustness of `AdaptiveTransferLearning` module on this "hard" dataset.
