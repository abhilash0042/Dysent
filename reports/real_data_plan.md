# Real CICDDoS2019 Validation Plan

## Goal

Validate the FL-DDoS system using the **actual** CICDDoS2019 dataset (not synthetic), ensuring robustness on real-world attack traffic.

## 1. Data Verification

- Check `ddosdfl/data` for `.csv` files (e.g., `DrDoS_DNS.csv`, `Syn.csv`).
- **Challenge**: The full dataset is >10GB.
- **Solution**: Use a representative subset (e.g., 100k samples) if full download is not feasible.

## 2. Data Preprocessing Script

Create `scripts/data/process_real_data.py`:

- Load raw CSVs.
- Select the 40 features used by the model.
- Handle missing values/infinity.
- Normalize/Scale (MinMax).
- Encode labels (Attack types).

## 3. Validation Test

Create `tests/test_real_cicddos2019_full.py`:

- **Load**: Processed real data.
- **Phase 1 (TL)**: Train Source Model on one attack type (e.g., DNS), Transfer to another (e.g., Syn).
- **Phase 2 (Meta)**: Test Few-Shot adaptation on a held-out attack (e.g., LDAP).
- **Metrics**: Accuracy, Precision, Recall, F1.

## 4. Execution

```bash
python scripts/data/process_real_data.py
python tests/test_real_cicddos2019_full.py
```

## Expected Outcome

- Proof that the system handles the **complexity and noise** of real network traffic.
- Validation of the 88%+ accuracy on real data.
