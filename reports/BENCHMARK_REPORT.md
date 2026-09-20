# ⚔️ Model Benchmark: Transformer vs. CNN-BiLSTM

**Dataset:** 30GB CICDDoS2019 (Sampled Mix)
**Training:** Epoch 1 (Early Stop for Speed)

---

## 1. Results

Both models were trained on the exact same dataset mix (~500,000 records).

| Feature             | Transformer      | CNN-BiLSTM        | Winner                     |
| :------------------ | :--------------- | :---------------- | :------------------------- |
| **Accuracy (Ep 1)** | 86.97%           | **97.79%**        | **CNN-BiLSTM**             |
| **Convergence**     | Slower Start     | **Instant**       | **CNN-BiLSTM**             |
| **Training Speed**  | ~80ms/step       | **~19ms/step**    | **CNN-BiLSTM (4x Faster)** |
| **Complexity**      | High (Attention) | Low (Conv + LSTM) | **CNN-BiLSTM**             |

## 2. Analysis

**Surprise Result:** The **CNN-BiLSTM outperformed the Transformer** in this specific test.

- **Why?**
  - **Simplicity:** Network traffic features ("Flow Duration", "Packet Size") are tabular and statistical. They don't have the deep, complex semantic relationships of natural language that Transformers excel at.
  - **Efficiency:** The CNN path (spatial features) instantly latches onto specific attack signatures (e.g., "High Packet Rate"), whereas the Transformer tries to learn complex relationships that might be overkill.
  - **Speed:** The CNN-BiLSTM trained **4x Faster**, making it much better for Edge/IoT deployment.

## 3. Recommendation

**Primary Model:** **CNN-BiLSTM**

- **Reason:** Higher accuracy, significantly faster, and lower resource usage. Perfect for real-time DDoS detection.

**Secondary Model:** **Transformer**

- **Reason:** Use for "Deep Analysis" of complex, low-volume traffic where CNNs fail.
