# Byzantine aggregation improvement results

Measured with a linear detector because `data/processed/cicddos2019_100k_reshaped_t10.npz` is not in this checkout.
Aggregation, clipping, and the attack suite are the same code the CNN runner now calls.

Config: {"profile": "paper", "command": "python experiments/federated_learning/run_byzantine_improved.py --profile paper", "clients": 20, "note": "Linear stand-in. CNN path uses aggregate_updates in run_real_byzantine_fl.py."}

Runs: 873 ({'success': 831, 'unsupported': 42}).

## Sign-flip F1 (mean over seeds, correct f, IID)

| Malicious | FedAvg | FedAvg+clip | Median | Multi-Krum | Trimmed mean |
|---|---:|---:|---:|---:|---:|
| 0% | 0.8007 | 0.8007 | 0.8008 | 0.8007 | 0.8007 |
| 10% | 0.7952 | 0.7952 | 0.7981 | 0.8001 | 0.7984 |
| 20% | 0.7944 | 0.7944 | 0.7935 | 0.7977 | 0.7941 |
| 30% | 0.7872 | 0.7872 | 0.7933 | 0.7995 | 0.7938 |
| 40% | 0.7584 | 0.7584 | 0.7888 | 0.7959 | 0.7909 |

## Sign-flip FPR

| Malicious | FedAvg | FedAvg+clip | Median |
|---|---:|---:|---:|
| 0% | 0.1861 | 0.1861 | 0.1878 |
| 10% | 0.1828 | 0.1828 | 0.1801 |
| 20% | 0.1763 | 0.1763 | 0.1819 |
| 30% | 0.1829 | 0.1829 | 0.1982 |
| 40% | 0.2000 | 0.2000 | 0.2026 |

## Runs that did not score

| Setting | Status | Count |
|---|---|---:|
| 30% adaptive bulyan non_iid=False | unsupported | 3 |
| 30% backdoor bulyan non_iid=False | unsupported | 3 |
| 30% gaussian bulyan non_iid=False | unsupported | 3 |
| 30% label_flip bulyan non_iid=False | unsupported | 3 |
| 30% random bulyan non_iid=False | unsupported | 3 |
| 30% scale bulyan non_iid=False | unsupported | 3 |
| 30% sign_flip bulyan non_iid=False | unsupported | 3 |
| 40% adaptive bulyan non_iid=False | unsupported | 3 |
| 40% backdoor bulyan non_iid=False | unsupported | 3 |
| 40% gaussian bulyan non_iid=False | unsupported | 3 |
| 40% label_flip bulyan non_iid=False | unsupported | 3 |
| 40% random bulyan non_iid=False | unsupported | 3 |
| 40% scale bulyan non_iid=False | unsupported | 3 |
| 40% sign_flip bulyan non_iid=False | unsupported | 3 |
