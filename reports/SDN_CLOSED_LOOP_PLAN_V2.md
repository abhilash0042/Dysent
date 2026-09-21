# SDN Closed-Loop DDoS Defense — Design Review and Revised Plan (v2)

Review of the v1 implementation plan, grounded in the actual state of this repository.
Every claim below was verified against the code and artifacts on disk.

---

## Part 0 — Executive summary

The v1 plan is a good *narrative* but it cannot be built as written. Three findings dominate:

1. **`models/fl_global_model_final.keras` is trained on leaked labels and must be retrained.**
   Two of its 40 input features are the CSV row index and the ground-truth Benign/Attack
   column. This is not a detail — it is the reason the model reports 98%+ accuracy, and it
   means the model has never learned to detect anything from traffic behaviour alone.

2. **The v1 telemetry design cannot produce the model's input.** The plan feeds a 6-value
   vector into a network that expects 40 specific StandardScaler-normalised CICFlowMeter
   columns, and reads them from a switch that (in standalone mode) has no per-IP flow
   entries to read.

3. **Several mitigation actions in v1 are self-defeating.** `block_signature` drops every
   SYN to the protected port, which finishes the denial of service on the attacker's behalf.

The revised plan below fixes the model first, replaces `ovs-ofctl` scraping with a real
OpenFlow 1.3 controller plus hybrid telemetry, and introduces a pluggable enforcement
backend so the same detector can run in Mininet (demo) or on a real Linux edge host
(actual protection).

---

## Part 1 — Verified findings

### Finding 1 (blocking): the model is trained on the label

`models/fl_global_model_final.keras` is a `CNN_BiLSTM` functional model:

| Property | Value |
| --- | --- |
| Input | `(None, 10, 4)` — 40 flat features split into 10 groups of 4 |
| Output | `Dense(18, softmax)` |
| Saved | keras 3.13.0, 2026-01-08 |

The 40 features come from `data/processed/cicddos2019_full_processed_feature_selection.pkl`
key `ensemble.indices`, indexing into the 79 columns in
`data/processed/cicddos2019_full_feature_extractor.pkl` key `feature_names`.

**Root cause.** `FeatureExtractor._identify_label_column` searches
`['label', 'Label', 'class', 'Class', ...]` and returns the *first* match:

```176:186:projects/shared_libs/data_processor.py
    def _identify_label_column(self, df: pd.DataFrame) -> str:
        """Identify the label column from common names"""
        possible_labels = ['label', 'Label', 'class', 'Class', 'attack', 'Attack']
        
        for col in possible_labels:
            if col in df.columns:
                return col
```

The source CSVs carry **two** label columns: `Label` (the 18-way attack name) and `Class`
(binary Benign/Attack). `Label` matched first, so only it was dropped at line 210 — `Class`
stayed in `X` and became input feature 78. Separately, `pd.read_csv` at line 54 is called
without `index_col=0`, so a previously saved index column was read in as the feature
`Unnamed: 0`.

Two of the 40 selected indices are therefore not features:

| Flat slot | Reshaped position | Source index | Column name | Problem |
| --- | --- | --- | --- | --- |
| 5 | timestep 1, channel 1 | 0 | `Unnamed: 0` | Pandas CSV row number. CICDDoS2019 files are grouped by attack type, so the row number all but names the class. |
| 31 | timestep 7, channel 3 | 78 | `Class` | The ground-truth binary Benign/Attack label. |

Column 78 is exactly binary and perfectly separates the classes:

```
value  1.84644 -> 97,831 rows, all label 0 (Benign)
value -0.54158 -> 333,540 rows, labels 1..17 (every attack class)
```

**Ablation** (20,000 random rows from `cicddos2019_full_processed.npz`, loaded model,
measured directly):

| Input condition | 18-class accuracy | Benign-vs-attack accuracy |
| --- | --- | --- |
| As trained (leak present) | **98.45 %** | **100.00 %** |
| Leak feature zeroed — what a live SDN can actually supply | 81.75 % | 83.29 % |
| Leak forced to "Benign" | 26.19 % | 26.19 % |
| Leak forced to "Attack" | 78.72 % | 80.27 % |
| Leak **and** row-index zeroed | **59.29 %** | **85.72 %** |

Read the last row against the first. The headline result is an artefact. A live detector can
never supply slots 5 and 31, so the honest operating point of this model today is ~59 %
multi-class / ~86 % binary — and the "leak forced to Benign" row shows an adversary who
merely looks normal on one dimension collapses it to 26 %.

This cannot be patched at inference time. **The model must be retrained.**

*Secondary consequence:* every accuracy figure in `EXPERIMENTAL_RESULTS.md`,
`reports/FINAL_RESULTS.md` and related documents inherits this leak and should be re-measured
after the retrain, not carried forward.

### Finding 2 (blocking): feature-contract mismatch

v1 proposes a 6-element vector: packet rate, byte rate, average packet size, SYN count,
flow duration, port number. The model requires 40 values, in a fixed order, standard-scaled
using a `StandardScaler` that was fitted on **79** columns (`scaler.n_features_in_ == 79`),
not on 6 and not on 40. v1 mentions no scaling step at all. Unscaled input to a
BatchNormalization-heavy network produces arbitrary output.

### Finding 3: output interpretation is wrong

v1 says "if prediction confidence > 0.85 → fire DDoS_ALERT". The model emits an 18-way
softmax, not a DDoS probability. The correct reading is `1 - p[0]`, where index 0 is `Benign`.

The full class list — which is an asset the plan does not exploit — is:

```
0  Benign        1  DrDoS_DNS    2  DrDoS_LDAP   3  DrDoS_MSSQL   4  DrDoS_NTP
5  DrDoS_NetBIOS 6  DrDoS_SNMP   7  DrDoS_UDP    8  LDAP          9  MSSQL
10 NetBIOS      11 Portmap      12 Syn          13 TFTP          14 UDP
15 UDP-lag      16 UDPLag       17 WebDDoS
```

The controller should use `argmax` to *name the attack* and pick a mitigation appropriate
to it. A `Syn` classification and a `WebDDoS` classification call for completely different
responses; v1 applies one drop rule to both.

### Finding 4 (blocking): the telemetry source cannot yield per-IP data

`experiments/mininet/run_simulation.py` builds the network with `controller=None` and then:

```34:34:experiments/mininet/run_simulation.py
        sw.cmd(f'ovs-vsctl set-fail-mode {sw.name} standalone')
```

In standalone mode OVS behaves as a MAC-learning L2 switch. `ovs-ofctl dump-flows s1`
returns essentially one entry with `actions=NORMAL`. There are no per-source-IP flow
entries, therefore no per-IP packet counts, byte counts or durations to extract. The v1
telemetry component reads data that does not exist.

`ovs-ofctl dump-ports` does work, but it is per-port only. In the v1 topology the attacker
sits on its own switch port, so a port counter alone identifies the attacker — the model
contributes nothing, and the approach fails the moment attackers share an uplink with real
users, which is the only case that matters in practice.

Separately, v1's overview says traffic is monitored "via OpenFlow telemetry (sFlow polling)"
but the telemetry component then uses `ovs-ofctl`. These are different mechanisms — sFlow is
sampled packet export pushed to a collector, `ovs-ofctl` is counter polling. The plan needs
to commit to both, deliberately (see Part 2).

### Finding 5: the OpenFlow commands contain runtime errors

| v1 command | Problem |
| --- | --- |
| `ovs-ofctl add-flow s1 "..."` after `set bridge s1 protocols=OpenFlow13` | Fails with a version-negotiation error. Requires `-O OpenFlow13` on every `ovs-ofctl` invocation. |
| `tcp_flags=SYN` | Not valid syntax. OVS expects `tcp_flags=+syn-ack`. |
| `idle_timeout=60, hard_timeout=300` on a drop rule | Backwards for a sustained flood: `idle_timeout` never fires while the attack continues, and `hard_timeout` then deletes the rule at 300 s **mid-attack**, re-exposing the server. Use `hard_timeout=0` with controller-driven revocation, or re-arm on expiry. |
| `rate_limit_port` via OpenFlow Meters | OVS meter support depends on datapath and version and is commonly unavailable under Mininet. Needs a `tc`/OVS-QoS fallback. |

### Finding 6: `block_signature` completes the attack

```
priority=60000,tcp,tcp_flags=SYN,nw_dst=10.0.0.254,tp_dst=8080,actions=drop
```

Every new TCP connection begins with a SYN. This rule blocks all *legitimate* new visitors
to the protected service for as long as it is installed. It does not mitigate the DDoS; it
achieves the attacker's goal with fewer packets. Correct handling of a spoofed SYN flood is
SYN cookies or a SYN proxy at the host, plus per-ingress-port rate limiting — never a
blanket SYN drop toward the service.

### Finding 7: per-IP rules do not survive spoofing

v1's `ip_spoof` attack mode uses random source addresses. Installing one `nw_src` drop rule
per observed source means thousands of flow-table entries within seconds, rule-installation
becomes the bottleneck, and the switch's table fills. Spoofed and botnet traffic must be
handled by rate/behaviour classes and ingress-port policing, not by enumeration.

### Finding 8: there is no controller in the design

v1 calls `sdn_controller.py` "the Python SDN Controller", but it is a wrapper that shells out
to `ovs-ofctl`. That is out-of-band switch configuration, not SDN — no OpenFlow channel, no
`packet_in`, no event loop, nothing a reviewer would accept as a control plane. For a project
whose contribution is SDN-based mitigation this is the weakest point in the whole plan.

### Finding 9: the Windows/WSL boundary is undefined

`dashboard/server.py` runs on Windows and serves port 5050, reading
`results/unified_pipeline/live_status.json`. The Mininet stack runs as root inside WSL. v1
says "Dashboard receives all this data via API" without specifying transport. From WSL2,
`localhost:5050` does not reach the Windows host by default. This needs an explicit decision.

### Finding 10: the environment is not provisioned

Checked in the `Ubuntu` WSL2 distro: `mn`, `ovs-vsctl`, `ovs-ofctl` and `ryu` are all absent;
only `/usr/bin/python3` exists. v1's execution section starts at
`sudo python3 run_sdn_defense.py`, which fails immediately.

One piece of good news: the WSL2 kernel **does** ship the datapath module —
`/lib/modules/6.6.87.2-microsoft-standard-WSL2/kernel/net/openvswitch/openvswitch.ko` is
present — so a kernel-datapath OVS is viable here and no custom kernel is required. The
userspace `netdev` datapath remains the fallback.

### Finding 11: the `(10, 4)` reshape is fake temporality

Splitting 40 unordered tabular columns into "10 timesteps of 4 features" creates a sequence
with no temporal meaning — timestep 3 is `Flow IAT Mean, Flow IAT Std, Flow Packets/s,
Fwd IAT Total` purely because of where they landed in the selection ranking. A CNN-BiLSTM
over that axis is modelling an artefact of array layout.

This is worth calling out because the SDN setting *hands you real sequences for free*: polling
each flow once per second naturally produces `T` consecutive observations of `F` features.
Using that would make the recurrent architecture genuinely justified rather than decorative.

### Finding 12: the validation protocol has no control and no false-positive measurement

The v1 verification table checks only that blocking happens. Missing: the same attack with
defense **disabled** (to show the app actually degrades without it), the false-positive rate
on legitimate bursty traffic (a flash crowd looks like an HTTP flood), and time-to-mitigate.
Without those three numbers the result is not evidence of anything.

### Finding 13: the measurement harness will be the bottleneck

Flask's development server is single-threaded. Under any real load it will queue and time out
for reasons unrelated to the DDoS or the defense, contaminating the "app stayed healthy"
claim. Response-time measurement also cannot live inside the app being measured.

### Finding 14: Mininet cannot protect "any website"

This is the requirement stated in the request, so it deserves a direct answer. Mininet is a
network *emulator*; hosts are network namespaces on one machine. Nothing in it can affect
traffic to a real site. Real protection requires the enforcement point to be **in the traffic
path** of the service you control. See Part 2.4.

---

## Part 2 — Revised architecture

### 2.1 Fix the model first (nothing else matters until this is done)

**Step 1 — leak-free feature pool.** Start from the 79 columns, remove `Unnamed: 0` (index 0)
and `Class` (index 78), then additionally constrain the pool to features that are *measurable
from network telemetry* before running selection. Selecting first and discovering
unmeasurability later is what produced the v1 mismatch.

Classification of the current ensemble-40 by what can actually be observed:

| Telemetry source | Count | Examples from the current 40 |
| --- | --- | --- |
| **Exact, from OpenFlow per-flow counters** (`duration`, `n_packets`, `n_bytes` on bidirectional 5-tuple entries) | ~18 | `Flow Duration`, `Total Fwd Packets`, `Total Backward Packets`, `Flow Bytes/s`, `Flow Packets/s`, `Fwd Packets/s`, `Bwd Packets/s`, `Avg Packet Size`, `Packet Length Mean`, `Avg Fwd Segment Size`, `Fwd Packets Length Total`, `Subflow Fwd Packets`, `Subflow Fwd Bytes`, `Protocol` |
| **Statistical, from sFlow sampled headers** | ~20 | `Packet Length Min/Max/Std/Variance`, `Fwd Packet Length Min/Max`, `ACK Flag Count`, `Init Fwd Win Bytes`, `Bwd Header Length`, `Fwd Act Data Packets`, IAT std/max terms |
| **Derivable from the poll cadence** | ~2 | `Idle Mean`, `Idle Std` |
| **Impossible — must be dropped** | 2 | `Unnamed: 0`, `Class` |

So roughly 38 of the 40 are recoverable *if* both telemetry channels are built. That is the
justification for the hybrid collector in 2.2, and it is why sFlow should be a real component
rather than a word in the overview.

**Step 2 — re-run selection and FL training.** Re-run the ensemble selection over the
constrained pool, take the top 40, and re-run `experiments/federated_learning/run_standard.py`
unchanged apart from the feature list. The federated training procedure, the CNN-BiLSTM
architecture and the blockchain audit trail all survive untouched — only the input contract
changes. Save as `models/fl_global_model_sdn.keras` and keep the old file for comparison.

**Step 3 — pin the contract.** Write `models/sdn_model_contract.json` containing the ordered
feature names, the source index list, scaler mean/scale for exactly those columns, the class
names, and the input shape. The controller loads this file and refuses to start if the model's
`input_shape` disagrees. This is the single guard that prevents the v1 failure mode from
recurring silently.

**Measured headroom (good news).** A RandomForest ceiling test on 120,000 rows, 70/30 split,
comparing the full 79 columns against the 77 leak-free ones:

| Task | With leak | Leak-free (77 features) |
| --- | --- | --- |
| Benign vs attack | 100.00 % | **99.86 %** |
| 18-class attack naming | 98.76 % | **93.27 %** |

The detection decision the SDN controller actually depends on — is this traffic an attack —
survives the fix almost untouched. Only fine-grained attack-type naming pays a real cost, and
93 % there is still strong. A single-feature scan over the remaining 77 columns found nothing
else above 97 % on its own, so there is no second hidden leak.

**Decision point — temporal representation.** Two options, please pick one:

- **Path A (fast, ~1 day):** keep the flat-40 → `(10, 4)` reshape. Minimal change, but
  Finding 11 stands and a sharp reviewer will raise it.
- **Path B (recommended, ~3 days):** build genuine sequences. Feature vector `F ≈ 12` per flow
  per 1 s poll, stacked over `T = 10` polls → input `(10, 12)`. Training data is produced by
  grouping CICDDoS2019 records into per-source windows. This makes the BiLSTM meaningful,
  matches exactly what the SDN collector emits, and gives the project a real contribution
  rather than a re-application.

### 2.2 Hybrid telemetry, with flows that actually exist

Replace "poll `dump-ports`, then scrape `dump-flows`" with three cooperating mechanisms:

1. **Reactive flow installation.** Run the switch in secure mode against a real controller.
   Unmatched traffic triggers `packet_in`; the controller installs a bidirectional 5-tuple
   entry with `flags=OFPFF_SEND_FLOW_REM`. Per-flow counters now exist, and they exist
   *because* the controller put them there.
2. **Counter polling** via `OFPFlowStatsRequest` at 1 s, giving exact volumetrics per flow.
   Deltas between polls give rates; this is the Tier-1 feature source.
3. **sFlow sampling** (`ovs-vsctl -- --id=@s create sFlow ...`, sampling 1-in-N) to a local
   collector, giving packet headers for length distributions, TCP flags and window sizes —
   the Tier-2 feature source.

Aggregation key must be **(source IP, destination IP, destination port, protocol)**, and
features must also be aggregated **per source IP** so that botnet and spoofing behaviour is
visible at the right granularity. Per-port aggregation alone is what made v1's detection
trivial-but-useless.

### 2.3 Graduated mitigation instead of a single drop rule

Map the model's class output and the observed source cardinality to a response, rather than
always installing a drop:

| Situation | Response | Rationale |
| --- | --- | --- |
| Single source, high confidence | `nw_src` drop, `hard_timeout=0`, controller-revoked | Precise and reversible |
| 5+ sources in one /24 | Single `nw_src=<prefix>/24` drop | One rule, bounded table growth |
| Many sources, low per-source rate (botnet) | Per-source-IP meter / QoS rate limit | Preserves any legitimate user caught in the range |
| Random spoofed sources | Ingress-port rate limit + **host SYN cookies**; never a blanket SYN drop | Enumeration is impossible; see Finding 6/7 |
| `WebDDoS` class (L7) | Per-source connection-rate limit, escalate to drop only on repeat | L7 floods use valid connections; dropping at L3 is too coarse |
| Confidence below threshold | Log and watch; do not act | Keeps false-positive cost at zero |

Every action must be reversible, must carry an expiry that the controller (not the switch)
owns, and must be written to the blockchain audit trail via the existing
`blockchain_interface.log_attack_detected` hook — which currently records a mitigation
*string* with no dataplane effect, and would finally become truthful.

### 2.4 Pluggable enforcement — this is what makes it work "on any website"

Define one interface and three implementations:

```
EnforcementBackend
  ├── block_source(ip, ttl)  ├── block_prefix(cidr, ttl)
  ├── rate_limit(selector, pps)  ├── revoke(rule_id)  └── stats()
```

| Backend | Mechanism | Use |
| --- | --- | --- |
| `MininetOvsBackend` | `ovs-ofctl -O OpenFlow13` / Ryu flow-mod | Reproducible demo and evaluation |
| `RyuOpenFlowBackend` | OpenFlow 1.3 to a real switch | Real SDN deployment |
| `NftablesBackend` | `nft add element ... @blocklist` on a real Linux host | **Real protection for a real website** |

The detector, the feature pipeline and the dashboard are identical across all three; only the
last hop differs. An `nftables` set drop is the practical equivalent of an OpenFlow drop, and
it works on an ordinary VPS.

**The honest constraint:** this protects sites whose traffic passes through a host you
control — your own server, or a box you place in front of it as an L3 forwarder or reverse
proxy. No host-resident system can protect a third-party website, and none of this defends
against volumetric floods that saturate your uplink *before* your NIC, which is the class of
attack that requires upstream/ISP scrubbing. Stating this limitation explicitly is stronger
than implying it was solved.

### 2.5 Dashboard transport

Pick one and make it explicit. Recommended: the WSL side writes
`results/sdn/live_sdn_status.json` to the shared `/mnt/c/projects/Dysent-1/...` path, and
`dashboard/server.py` reads it the same way `/api/status` already reads `live_status.json`.
This reuses the working pattern, needs no cross-OS networking, and keeps the root-owned
Mininet process isolated from the web server. Writes must be atomic (write to a temp file,
then rename) or the dashboard will intermittently read half-written JSON.

---

## Part 3 — Implementation phases

Each phase has an acceptance test. Do not start a phase before its predecessor passes.

### Phase 0 — Environment (half a day)

Install `mininet`, `openvswitch-switch`, `python3-ryu` (or `ryu` via pip in a venv),
`hping3`, `tcpdump` in WSL Ubuntu. Verify the kernel datapath loads.

*Accept:* `sudo mn --test pingall --switch ovsk,protocols=OpenFlow13` passes, and
`ovs-ofctl -O OpenFlow13 dump-flows s1` returns without a version error.

### Phase 1 — Leak-free model (1 day, Path A / 3 days, Path B)

Constrained feature pool → re-selection → federated retrain → `sdn_model_contract.json`.

*Accept:* the ablation from Finding 1 is re-run against the new model and the delta between
"as trained" and "all live-unavailable features zeroed" is **zero**, because no such features
remain. Report the new honest accuracy.

*Files:* `experiments/feature_selection/run_sdn_constrained.py`,
`experiments/federated_learning/run_standard.py` (feature-list parameter),
`models/sdn_model_contract.json`.

### Phase 2 — Telemetry and feature exporter (2 days)

Ryu app with reactive flow install; 1 s `OFPFlowStatsRequest` poller; sFlow collector;
aggregator producing the exact ordered feature vector from the contract, scaled with the
pinned scaler parameters.

*Accept:* replay a labelled CICDDoS2019 slice through Mininet, export features live, and show
mean absolute error per feature against the dataset's own values for that traffic. If the
exporter does not reproduce the training distribution, the model will not transfer — this is
the test that catches it before it becomes a mystery.

*Files:* `projects/sdn/telemetry_openflow.py`, `projects/sdn/telemetry_sflow.py`,
`projects/sdn/feature_exporter.py`.

### Phase 3 — Detector (1 day)

Load model + contract, sliding window per flow key, `1 - p[Benign]` for the alarm,
`argmax` for the attack name, hysteresis (N consecutive windows over threshold) to suppress
single-window false positives, plus per-source and per-/24 aggregation for botnet grouping.

*Accept:* on replayed labelled traffic, report precision/recall/FPR per attack class and the
detection latency distribution.

*Files:* `projects/sdn/detector.py`.

### Phase 4 — Controller and enforcement (2 days)

Ryu application implementing the graduated ladder in 2.3, the `EnforcementBackend` interface,
controller-owned rule lifecycle with revocation, and the blockchain audit hook.

*Accept:* `ovs-ofctl -O OpenFlow13 dump-flows s1` shows the expected rule with a rising
`n_packets`; `tcpdump` on `h_server-eth0` shows zero attacker packets after mitigation;
revocation removes the rule and traffic resumes.

*Files:* `projects/sdn/controller_app.py`, `projects/sdn/enforcement/{base,ovs,nftables}.py`.

### Phase 5 — Topology, workload and attacks (1 day)

Two-switch topology so that legitimate and attack traffic **share** an uplink port — this is
what forces the detector to do real work and prevents the port-counter shortcut.

Protected service: a threaded HTTP server (not the Flask dev server). Keep it minimal, per the
request — it is a target, not a deliverable.

Load generation must be **out-of-band**: a separate client host measures latency and error
rate, so the measurement does not share a process with the thing under attack.

Attacks: `syn_flood`, `udp_flood`, `http_flood`, `botnet_sim`, `ip_spoof` — plus a
**flash-crowd** generator of legitimate bursty traffic, which is the false-positive test.

*Files:* `experiments/mininet/sdn_topology.py`, `experiments/mininet/target_service.py`,
`experiments/mininet/load_client.py`, `experiments/mininet/attacker.py`.

### Phase 6 — Orchestration, dashboard, evaluation (2 days)

Runner, atomic JSON status writer, `/api/sdn/status` and `/api/sdn/alerts` endpoints, dashboard
panel.

*Files:* `experiments/mininet/run_sdn_defense.py`, `dashboard/server.py`,
`dashboard/live_dashboard.html`.

---

## Part 4 — Validation protocol

Every run produces these numbers, for each attack type, with and without defense:

| Metric | Why it matters |
| --- | --- |
| **Defense OFF**: p50/p99 latency, error rate under attack | The control. Without it there is no evidence the defense did anything. |
| **Defense ON**: p50/p99 latency, error rate under attack | The result. |
| **Time to mitigate** (first attack packet → rule installed) | The real cost of a 1 s poll interval. v1's "wire speed" claim only holds *after* this window. |
| **Attack packets reaching the server** before and after | Measured with `tcpdump`, not inferred from counters. |
| **False-positive rate** on the flash-crowd workload | The number that decides whether this is deployable. |
| **Rules installed** per attack type | Detects flow-table explosion under spoofing. |
| **Detector precision/recall per class** | Ties the SDN result back to the ML contribution. |

A result is only reportable if the defense-off control shows genuine degradation. If the
service survives the attack with the defense disabled, the attack was too weak and the
experiment proves nothing.

---

## Part 5 — What changed from v1, at a glance

| v1 | v2 | Reason |
| --- | --- | --- |
| Reuse `fl_global_model_final.keras` | Retrain leak-free, pin an explicit contract | Finding 1 — current model reads the label |
| 6 hand-picked features | Contract-defined 40, selected only from measurable columns | Finding 2 |
| `confidence > 0.85` | `1 - p[Benign]`, `argmax` names the attack | Finding 3 |
| `ovs-ofctl dump-ports/dump-flows` | Ryu + reactive flow install + flow-stats + sFlow | Finding 4 |
| `ovs-ofctl` shell wrapper "controller" | Real OpenFlow 1.3 control plane | Finding 8 |
| One drop rule for everything | Graduated, class-aware, reversible ladder | Findings 3, 6, 7 |
| Blanket SYN drop for spoofing | Rate limiting + SYN cookies | Finding 6 |
| `idle=60, hard=300` | Controller-owned lifecycle, `hard_timeout=0` | Finding 5 |
| Attacker on a dedicated port | Shared uplink, two-switch topology | Finding 4 |
| Mininet only | Pluggable backend incl. `nftables` for real hosts | Finding 14 |
| "Dashboard receives data via API" | Atomic JSON on the shared `/mnt/c` path | Finding 9 |
| Verification = "blocking happened" | Defense-off control, FPR, time-to-mitigate | Finding 12 |

---

## Open decisions

1. **Path A or Path B** for the temporal representation (section 2.1).
2. **Real-deployment target** — is the `nftables` backend in scope now, or is the Mininet
   demo sufficient for this milestone?
3. **Re-measurement scope** — should the existing result documents be re-run against the
   leak-free model, or annotated with the correction?
