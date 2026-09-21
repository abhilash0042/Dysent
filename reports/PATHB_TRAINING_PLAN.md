# Path-B Training Plan — 1-second sequence model for SDN

This is the training recipe for the **closed-loop SDN detector**.
It does **not** reuse `fl_global_model_final.keras` (label leak + fake `(10, 4)` reshape).

---

## What the data is now

CICDDoS2019 has **no dedicated BENIGN.csv**. Benign is mixed into each attack file.
We downloaded a small official file (`03-11/Portmap.csv`) and kept **only BENIGN rows**,
then rebuilt windows as **1-second buckets per Source IP** (what the SDN poller will emit).

| Artifact | Path | Role |
|---|---|---|
| Raw subset | `data/raw/cicddos2019_subset/` | CSVs with Timestamp + Source IP |
| Extra benign | `BENIGN_from_Portmap.csv` (4,734 rows) | Official day-2 background traffic |
| Windows | `data/processed/cicddos2019_temporal_windows.npz` | Training tensor |
| Contract | `data/processed/cicddos2019_leakfree_feature_extractor.pkl` | Scaler + 18 class names |
| Features | `data/processed/cicddos2019_leakfree_feature_selection.pkl` | Same 40 names, no leaks |

**Tensor:** `(6866, 10, 40)`

- `10` = ten consecutive **1-second** observations of the same source IP  
- `40` = leak-free CIC features, already StandardScaled with the leak-free scaler  
- Overlapping stride = 1 second (more samples without changing the clock)

### Class mix (after option 1 + 3)

| Class | Windows | Share |
|---|---:|---:|
| Benign | **1,026** | **14.9%** |
| TFTP | 1,322 | 19.3% |
| DrDoS_NTP | 724 | 10.5% |
| DrDoS_DNS | 687 | 10.0% |
| DrDoS_UDP | 676 | 9.8% |
| DrDoS_MSSQL | 594 | 8.7% |
| DrDoS_LDAP | 583 | 8.5% |
| DrDoS_NetBIOS | 578 | 8.4% |
| UDP-lag | 447 | 6.5% |
| Syn | 229 | 3.3% |

Was **51 / 14,975 (0.3%)**. Now **1,026 / 6,866 (~15%)**.

Still missing in this subset (do not expect the model to name them):  
`DrDoS_SNMP`, `LDAP`, `MSSQL`, `NetBIOS`, `Portmap`, `UDP`, `UDPLag`, `WebDDoS`.  
For SDN they map to the nearest family at inference (`UDP` → `DrDoS_UDP`, `UDPLag` → `UDP-lag`).

---

## How this matches live SDN

```
every 1s, per Source IP:
  OpenFlow counters + sFlow headers
       ↓
  40 leak-free features, same scaler
       ↓
  append to a 10-second ring buffer  →  shape (1, 10, 40)
       ↓
  model.predict  →  18-way softmax
```

Training windows **are** that ring buffer. No reshape hack.

Live interpretation:

```
p = softmax
attack_score = 1 - p[Benign]          # index 0
attack_name  = class_names[argmax(p)]
fire if attack_score > T AND telemetry pps > baseline
```

Do **not** use `max(p) > 0.85` as “DDoS confidence”.

---

## Training rules (do not skip)

1. **Do not load** `fl_global_model_final.keras`. New architecture input is `(10, 40)`, not `(10, 4)`.
2. **Do not fit a new scaler.** Use the leak-free `StandardScaler` already applied in the NPZ.
3. **Do not random-split overlapping windows.** Consecutive stride-1 windows from the same IP leak into train and test. Split by **Source IP groups** or by **time** (first 70% of each IP’s timeline = train).
4. **Keep 18-class softmax** so the dashboard can name Syn vs UDP vs DNS. For mitigation, threshold on `1 - p[Benign]`.
5. **Class weights** (or balanced sampler). Syn is 3.3%; TFTP is 19%. Unweighted training will ignore SYN floods.
6. **Two-stage in production:** rate spike first, model second. That is what makes “normal traffic looks different from floods” actually safe.

---

## Recommended recipe

### Model

Reuse `CNNBiLSTMModel` with:

```
input_shape = (10, 40)
num_classes = 18          # same LabelEncoder as leak-free extractor
cnn_filters = (64, 128)
lstm_units  = (64, 32)
dropout     = 0.5
loss        = sparse_categorical_crossentropy
```

Save as `models/fl_global_model_pathb.keras` — never overwrite `fl_global_model_final.keras`.

### Split (source-safe)

For each Source IP timeline:

- first 70% of windows → train  
- next 15% → val  
- last 15% → test  

If an IP has < 4 windows, put it entirely in train. This blocks stride-1 leakage.

### Class weights

```
w_c = N / (C * n_c)
```

Cap the max weight at ~8 so rare Syn does not explode the loss.

### Federated (optional, for the paper)

3 nodes, Non-IID by attack family:

| Node | Data |
|---|---|
| node_1 | Syn + TFTP + Benign/3 |
| node_2 | DrDoS_DNS + NTP + LDAP + Benign/3 |
| node_3 | DrDoS_UDP + UDP-lag + MSSQL + NetBIOS + Benign/3 |

FedAvg, 15 rounds, 3 local epochs. Compare to one centralised run on the same split.

### Thresholds (set on val, freeze for test)

| Output | Use |
|---|---|
| `attack_score > 0.80` | default SDN alert |
| `attack_score > 0.90` | hard drop |
| `0.60–0.80` | rate-limit only |
| below 0.60 | log, do not block |

Tune the 0.80 cut so **false-positive rate on Benign val windows < 5%**.

---

## Metrics that actually matter for SDN

| Metric | Pass bar |
|---|---|
| Benign recall (1 − FPR) | ≥ 95% on val/test |
| Attack recall (binary) | ≥ 95% |
| Syn recall | ≥ 90% (your main demo flood) |
| Time-to-mitigate (simulated) | ≤ 10 s (window fill) + 1 s poll |
| Per-class confusion | no systematic Benign → Syn |

Do **not** report 18-class accuracy as the headline. Report **binary detection + FPR**, then per-attack naming as a second table.

---

## Run order

```
# 1. Data already built
python scripts/build_temporal_windows.py --timesteps 10 --stride 1

# 2. Train Path-B (to be added: experiments/federated_learning/run_pathb.py)
python experiments/federated_learning/run_pathb.py --central
python experiments/federated_learning/run_pathb.py --federated --nodes 3 --rounds 15

# 3. Pin contract after a passing run
# models/sdn_model_contract.json
#   input_shape [10, 40]
#   feature_names = leak-free 40
#   class_names   = leak-free 18
#   scaler mean/scale from leak-free extractor
#   model_path models/fl_global_model_pathb.keras

# 4. Only then start SDN controller (Phase 2+)
```

---

## Honest limits (write these in the report)

- 6,866 windows is a **small** sequence set. Good for a closed-loop demo, not a SOTA CIC leaderboard claim.
- 8 of 18 CIC classes are absent; naming them is out of scope until more CSVs are added.
- Overlapping windows inflate sample count; source-safe split is mandatory or numbers lie.
- Live OpenFlow features will still differ slightly from CICFlowMeter. After Mininet collector exists, **fine-tune** Path-B on collector-labeled traffic (domain adaptation). That is the last accuracy jump.

---

## What not to train

| Job | Dataset | Why |
|---|---|---|
| Leak-free flat baseline | `cicddos2019_leakfree_processed.npz` + selection pkl | optional A/B vs Path-B |
| Path-B SDN model | `cicddos2019_temporal_windows.npz` | this plan |
| Old leaked model | `cicddos2019_full_processed.npz` | do not retrain |

If both A and B are trained, compare **binary FPR and Syn recall** on the same held-out IPs, not 18-class accuracy.
