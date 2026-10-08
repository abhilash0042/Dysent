"""Generate the P2P (decentralized) FL implementation plan as .docx."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Cm

OUT = Path(__file__).resolve().parents[1] / "reports" / "IMPLEMENTATION_PLAN_P2P_FL.docx"

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
MUTED = RGBColor(0x4A, 0x4A, 0x4A)
GREEN = RGBColor(0x1B, 0x5E, 0x20)


def set_run_font(run, name="Calibri", size=11, bold=False, color=None, italic=False):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def add_heading_styled(doc, text, level):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.color.rgb = NAVY if level <= 1 else ACCENT
        run.font.name = "Calibri"
    return p


def add_para(doc, text, *, bold=False, italic=False, size=11, space_after=8, color=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    set_run_font(run, size=size, bold=bold, italic=italic, color=color or MUTED)
    return p


def add_bullets(doc, items, numbered=False):
    style = "List Number" if numbered else "List Bullet"
    for item in items:
        p = doc.add_paragraph(item, style=style)
        p.paragraph_format.space_after = Pt(3)
        for run in p.runs:
            set_run_font(run, size=11, color=MUTED)


def shade_header_row(row, fill="1F4E79"):
    for cell in row.cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), fill)
        shd.set(qn("w:val"), "clear")
        tcPr.append(shd)
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.font.size = Pt(10)
                run.font.name = "Calibri"


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        hdr.cells[i].text = h
    shade_header_row(hdr)
    for r_i, row in enumerate(rows):
        for c_i, val in enumerate(row):
            cell = table.rows[r_i + 1].cells[c_i]
            cell.text = str(val)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    set_run_font(run, size=10, color=MUTED)
    doc.add_paragraph()
    return table


def example_box(doc, title, body_lines):
    add_para(doc, f"Example — {title}", bold=True, size=11, color=ACCENT, space_after=4)
    for line in body_lines:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.5)
        run = p.add_run(line)
        set_run_font(run, name="Consolas", size=9, color=MUTED)


def expected(doc, items):
    add_para(doc, "Expected output (done when…)", bold=True, size=11, color=GREEN, space_after=4)
    add_bullets(doc, items)


def build():
    doc = Document()

    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = fp.add_run(
            "Dysent-1  |  P2P Federated Learning Implementation Plan  |  Keep centralized FedAvg; add comparable gossip path"
        )
        set_run_font(r, size=8, color=RGBColor(0x88, 0x88, 0x88), italic=True)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_after = Pt(4)
    r = t.add_run("Implementation Plan")
    set_run_font(r, size=26, bold=True, color=NAVY)

    st = doc.add_paragraph()
    st.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st.paragraph_format.space_after = Pt(4)
    r = st.add_run("Fully Decentralized (P2P) Federated Learning")
    set_run_font(r, size=16, color=ACCENT)

    st2 = doc.add_paragraph()
    st2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st2.paragraph_format.space_after = Pt(10)
    r = st2.add_run(
        "Permissioned gossip among organizations  ·  Centralized FedAvg kept as baseline  ·  Same data, same CNN-BiLSTM, side-by-side results"
    )
    set_run_font(r, size=11, italic=True, color=MUTED)

    add_para(
        doc,
        "This plan is an implementation specification, not a research outline. "
        "Each task says what to build, how it behaves in a real multi-organization "
        "deployment, a concrete numerical example, and the artifact that proves the task is done. "
        "Centralized FedAvg stays. P2P is a second training path. The paper/demo story is the comparison.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "1. Decision and non-goals", 1)
    add_para(
        doc,
        "Decision. Keep FederatedServer / run_standard.py unchanged. Add a parallel P2P path "
        "(GossipNode + overlay + experiment runner) that never calls FederatedServer. "
        "Compare both on identical data splits, model architecture, epochs, and held-out test set.",
    )
    add_para(doc, "What “real world” means in this project", bold=True)
    add_para(
        doc,
        "We are not claiming open-Internet, permissionless FL among strangers. "
        "Real world here means: each organization is a separate process (later a separate host), "
        "holds private CIC-DDoS2019 (or live-flow) data that never leaves the site, "
        "exchanges model weights only with named neighbors over TCP, survives a crashed peer, "
        "and can export a .keras file the existing SDN controller can load. "
        "That is how campuses, ISPs, or SOC partners would actually run this: a small permissioned overlay, not BitTorrent.",
    )
    add_table(
        doc,
        ["Do", "Do not"],
        [
            [
                "Keep centralized FedAvg as the reference experiment",
                "Delete or rewrite aggregation_server.py",
            ],
            [
                "Each org process owns its data and model copy",
                "Pass numpy arrays between Python objects and call it P2P",
            ],
            [
                "Static neighbor list of known orgs (permissioned)",
                "DHT / open peer discovery / public Internet FL",
            ],
            [
                "TCP length-prefixed messages (reuse Mininet framing)",
                "Put full weights on Fabric chaincode",
            ],
            [
                "Export converged model to SDN contract when P2P FPR is acceptable",
                "Force SDN to use a worse P2P model just to say it is live",
            ],
            [
                "Grep gate: P2P runner must not import FederatedServer",
                "Elect a hidden leader or “coordinator” that still averages everyone",
            ],
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "2. What exists today (baseline you keep)", 1)
    add_para(
        doc,
        "Topology is a star. Five simulated organizations (node_1 … node_5) train CNN-BiLSTM locally. "
        "A single FederatedServer collects all weights and computes data-size-weighted FedAvg:",
    )
    add_para(doc, "w_global = Σ (n_k / N) · w_k", italic=True)
    add_table(
        doc,
        ["Piece", "Path", "Role after this plan"],
        [
            ["FederatedServer", "projects/fl/aggregation_server.py", "Unchanged. Central baseline."],
            ["FLNode", "projects/fl/fl_node_client.py", "Reuse local train + weight get/set."],
            ["run_standard.py", "experiments/federated_learning/", "Keep. Produce baseline JSON."],
            ["Mininet TCP", "experiments/mininet/mininet_*.py", "Reuse send_msg/recv_msg framing."],
            ["LocalTrainer deltas/hash", "projects/fl_node/local_trainer.py", "P2P v1.1: send Δw + SHA-256."],
            ["Krum / TrimmedMean", "projects/shared_libs/byzantine_defense.py", "Neighbor-set robust mix (Phase 4)."],
            ["TrustManager", "projects/shared_libs/trust_manager.py", "Reject unsigned / low-trust peers."],
            ["Fabric fl-audit", "fabric/chaincode/fl-audit/", "Commit hashes + round metrics, not weights."],
            ["SDN contract", "models/sdn_model_contract.json", "Hot-swap only after P2P FPR gate."],
            ["gossip_node.py", "does not exist", "Build this. Core of P2P."],
        ],
    )
    add_para(
        doc,
        "Known SDN fact to respect: Path B currently deploys fl_global_model_pathb_central.keras because "
        "centralized FedAvg test FPR was 20.8% vs central 0.5%. P2P must not silently replace that file. "
        "Export a separate artifact (fl_global_model_pathb_p2p.keras) and switch the contract only if FPR is competitive.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "3. Real-world mapping (organizations, not Python objects)", 1)
    add_para(
        doc,
        "Think of five partner SOCs that agree to share DDoS detectors but not packet traces. "
        "Each site is a legal entity. Traffic stays on-prem. Only model parameters move, and only to named peers.",
    )
    add_table(
        doc,
        ["Org ID", "Real-world analogue", "Private data", "Bind address (lab)", "Neighbors (ring v1)"],
        [
            ["org_campus", "University campus SOC", "East-campus NetFlow / CIC slice A", "10.0.1.11:9101", "org_isp, org_cloud"],
            ["org_isp", "Regional ISP NOC", "Access-edge DDoS traces, slice B", "10.0.1.12:9101", "org_campus, org_bank"],
            ["org_bank", "Bank SOC", "Datacenter flows, slice C (more Web/Syn)", "10.0.1.13:9101", "org_isp, org_cloud"],
            ["org_cloud", "Cloud tenant defender", "East-west + public VIP floods, slice D", "10.0.1.14:9101", "org_bank, org_gov"],
            ["org_gov", "Gov CERT", "National IXP sample, slice E", "10.0.1.15:9101", "org_cloud, org_campus"],
        ],
    )
    add_para(
        doc,
        "In Phase 1 (in-process), these are five threads with an explicit neighbor graph so the algorithm is identical. "
        "In Phase 3 (process-per-org), each row is a real OS process on 127.0.0.1 with a different port. "
        "In Phase 5 (Mininet), each row is a host (h1–h5) on a data-plane overlay. Same protocol, three fidelities.",
    )
    example_box(
        doc,
        "One real round at org_isp",
        [
            "1. org_isp trains 2 local epochs on its private 12,400 flows. Weights stay in RAM.",
            "2. It opens TCP to org_campus:9101 and org_bank:9101 (only those two).",
            "3. Message GOSSIP_PUSH: {org_id, round, n_samples: 12400, sha256, weights or delta}.",
            "4. Each neighbor replies GOSSIP_PULL with its current weights + n_samples.",
            "5. org_isp mixes: w ← (n_i·w_i + n_j·w_j) / (n_i + n_j) for each accepted neighbor, sequentially.",
            "6. Raw PCAP never leaves org_isp. Fabric (optional) stores only sha256 + round + org_id.",
            "7. After round 20, org_isp evaluates a frozen held-out test set (same file as FedAvg).",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "4. Algorithms (v1 required, v2 optional)", 1)
    add_heading_styled(doc, "4.1 Central baseline (already implemented) — FedAvg", 2)
    add_para(
        doc,
        "Server waits until all selected nodes send updates. One weighted average. Everyone loads the same global weights. "
        "Synchronous. Single point of failure. Best-case accuracy for a given communication budget.",
    )
    add_heading_styled(doc, "4.2 P2P v1 — periodic gossip with size-weighted pair mix (required)", 2)
    add_para(
        doc,
        "Each org, each round: train locally, then exchange with a subset of neighbors (fanout = 2 on a ring+chords). "
        "Mix is data-size weighted so a tiny org cannot drag a large ISP. Sequential pair mixes approximate FedAvg as mixing continues.",
    )
    example_box(
        doc,
        "Numeric mix (one layer scalar, for intuition)",
        [
            "org_isp:   w=0.80, n=10_000",
            "org_bank:  w=0.20, n= 2_000",
            "mix at isp after talking to bank:",
            "  w' = (10000*0.80 + 2000*0.20) / 12000 = 0.70",
            "If they used naive (w + w_j)/2 they would get 0.50 — that is wrong when n differs.",
            "Always weight by n_samples. Store n_samples in the message.",
        ],
    )
    add_para(
        doc,
        "Round barrier (lab). For a fair comparison against FedAvg, the first P2P experiment uses a logical round index. "
        "Each org trains, then gossips fanout times, then evaluates. That is still P2P (no server averages all weights) "
        "but comparable. Async gossip without a barrier is Phase 6, not v1.",
    )
    add_heading_styled(doc, "4.3 P2P v2 — push-sum (optional if v1 F1 gap > 5 points)", 2)
    add_para(
        doc,
        "Each node keeps a mass s (weights × n) and a weight p (n). Gossip sends (s/2, p/2) to a neighbor and keeps half. "
        "The unbiased estimate is s/p. Use this if v1 under-weights large orgs on non-IID splits. Do not start v2 until v1 comparison JSON exists.",
    )
    add_heading_styled(doc, "4.4 Probe model (how you measure “global” without a server)", 2)
    add_para(
        doc,
        "There is no global model in P2P. For plots, define probe_weights as the simple average of all honest orgs’ current weights "
        "computed only in the experiment harness after the round (offline, not during training). "
        "Also report per-org F1 on the shared test set. Both numbers go in the comparison table. "
        "The harness average is an evaluation trick, not a training aggregator. The P2P runner still must not import FederatedServer.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "5. Protocol (what actually goes on the wire)", 1)
    add_para(
        doc,
        "Reuse Mininet length-prefix: 4-byte big-endian length + pickle (lab) / msgpack (later). "
        "TLS is Phase 5. Lab v1 may be plaintext on loopback. Production claim requires TLS + org certificates.",
    )
    add_table(
        doc,
        ["Type", "Direction", "Payload", "When"],
        [
            ["HELLO", "A → B", "org_id, pubkey fingerprint, protocol_version=1", "Connect"],
            ["HELLO_ACK", "B → A", "org_id, accepted / reject reason", "Connect"],
            ["GOSSIP_PUSH", "A → B", "round, n_samples, sha256, weights[] or delta[], mix_mass", "Each mix"],
            ["GOSSIP_PULL", "B → A", "same fields for B’s current model", "Reply to PUSH"],
            ["NACK", "B → A", "reason: hash_mismatch | round_skew | size_clip | untrusted", "Reject mix"],
            ["HEARTBEAT", "A ↔ B", "round, uptime_s", "Every 5 s"],
            ["BYE", "A → B", "reason", "Shutdown"],
        ],
    )
    add_para(doc, "Hard limits (real-world safety)", bold=True)
    add_bullets(
        doc,
        [
            "Max message 64 MiB. CNN-BiLSTM weights for (10,40) input are well under this; reject anything larger.",
            "Reject if |round_A − round_B| > 2 (stale / replay).",
            "Reject if ||Δw||_2 > τ (τ from config, default: 10× median of last 5 honest deltas in sim).",
            "Timeout 15 s per neighbor; skip and continue. Log skipped_peers.",
            "Never mix with an org not in the static allow-list.",
        ],
    )
    example_box(
        doc,
        "config/p2p_topology.yaml (v1 ring with one extra chord)",
        [
            "protocol_version: 1",
            "fanout: 2",
            "local_epochs: 2",
            "rounds: 20",
            "mix_rule: size_weighted_pair",
            "max_msg_bytes: 67108864",
            "round_skew_max: 2",
            "orgs:",
            "  - id: org_campus",
            "    host: 127.0.0.1",
            "    port: 9101",
            "    data_shard: data/p2p_shards/org_campus.npz",
            "    neighbors: [org_isp, org_gov]",
            "  - id: org_isp",
            "    host: 127.0.0.1",
            "    port: 9102",
            "    data_shard: data/p2p_shards/org_isp.npz",
            "    neighbors: [org_campus, org_bank]",
            "  # … org_bank 9103, org_cloud 9104, org_gov 9105",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "6. Comparison protocol (this is the scientific contract)", 1)
    add_para(
        doc,
        "If this is sloppy, P2P will look better or worse for accidental reasons. Freeze these knobs for both paths.",
    )
    add_table(
        doc,
        ["Knob", "Frozen value", "Why"],
        [
            ["Model", "Same CNN-BiLSTM builder as run_standard.py", "Architecture must not change"],
            ["Features", "40 ensemble features, timesteps=10", "Match SDN contract input"],
            ["Data", "Same CIC split, same seed 42, 5 shards", "P2P shard i == FedAvg node_i"],
            ["IID and Non-IID", "Run both; Non-IID is the real-world case", "SOCs do not see the same attacks"],
            ["Local epochs / round", "2 (P2P) vs 5 (FedAvg) is NOT allowed as a silent change", "Set both to 2 for the comparison table; optionally also report FedAvg@5 as extra row"],
            ["Rounds", "20", "Match fl_config.yaml"],
            ["Batch size / LR", "64 / 0.001", "Match fl_config.yaml"],
            ["Test set", "One held-out 15% never used for mix", "Fair F1 / FPR"],
            ["Seeds", "42, 43, 44 (three runs, mean±std)", "Gossip is noisier; one seed is not enough"],
        ],
    )
    add_para(doc, "Primary metrics (must appear in results/p2p/comparison.json)", bold=True)
    add_table(
        doc,
        ["Metric", "How", "Pass bar (honest data, IID)"],
        [
            ["Macro-F1 (probe)", "Held-out test, probe = mean of org weights", "P2P within 5 F1 points of FedAvg@same epochs"],
            ["Macro-F1 (worst org)", "Min over honest orgs", "Document gap; Non-IID will be larger"],
            ["FPR (Benign)", "False attack rate on benign test rows", "Must not exceed FedAvg by >5 points without explanation; SDN switch requires FPR ≤ 2%"],
            ["Rounds to F1≥0.90", "First round hitting the bar", "P2P may need more rounds; that is a valid result"],
            ["Bytes / org / round", "Sum of PUSH+PULL payloads", "Expect ~2× fanout vs 1× server upload; report MB"],
            ["Wall time / round", "Max org time including timeouts", "P2P should survive 1 dead neighbor without hanging"],
            ["Partition resilience", "Kill 1 org at round 10", "Remaining 4 still mix; F1 drop documented"],
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "7. Work breakdown — phases, tasks, examples, expected output", 1)
    add_para(
        doc,
        "Do phases in order. Do not start Mininet P2P until in-process comparison JSON exists. "
        "Do not start TLS or Fabric until process-per-org gossip works on loopback.",
    )

    # Phase 0
    add_heading_styled(doc, "Phase 0 — Freeze the centralized baseline (do not modify the server)", 2)
    add_para(doc, "Goal. A dated FedAvg result file you will never “accidentally” re-tune while building P2P.", bold=True)
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "Run experiments/federated_learning/run_standard.py with seed 42, 43, 44 on the same shard recipe you will use for P2P (write a shared split_data_for_orgs helper if run_standard currently splits inline).",
            "Save models/baselines/fedavg_seed{42,43,44}.keras and results/p2p/baseline_fedavg.json (per-round loss, acc, F1, FPR, bytes estimate).",
            "Record local_epochs actually used. If it is 5, either re-run FedAvg at 2 epochs for apples-to-apples or add a second baseline row. Do not hide this.",
            "Leave aggregation_server.py and FLNode public methods stable; P2P will call train_local_model / get weights / set weights only.",
        ],
        numbered=True,
    )
    example_box(
        doc,
        "baseline_fedavg.json fragment",
        [
            '{ "mode": "fedavg", "seed": 42, "local_epochs": 2, "rounds": 20,',
            '  "num_orgs": 5, "iid": true,',
            '  "rounds_log": [ {"round": 1, "macro_f1": 0.71, "fpr": 0.08}, ... ],',
            '  "final": {"macro_f1": 0.96, "fpr": 0.012, "bytes_per_round_mb": 18.4} }',
        ],
    )
    expected(
        doc,
        [
            "Three FedAvg JSON files exist and git-ignored or stored under results/p2p/baseline/.",
            "You can state one sentence: “FedAvg seed 42, 2 local epochs, 20 rounds, macro-F1 = X, FPR = Y.”",
            "No code change required in FederatedServer.",
        ],
    )

    # Phase 1
    add_heading_styled(doc, "Phase 1 — In-process gossip (algorithm correctness, still no sockets)", 2)
    add_para(
        doc,
        "Goal. Prove pair-mix math and the neighbor graph without debugging TCP. "
        "This is still “P2P” in the training sense (no FederatedServer.federated_averaging). "
        "Communication is a Python queue keyed by org_id, which you will replace with sockets in Phase 3 without changing GossipNode.step().",
        bold=False,
    )
    add_para(doc, "Files to create", bold=True)
    add_table(
        doc,
        ["File", "Responsibility"],
        [
            ["config/p2p_topology.yaml", "Org ids, neighbors, ports, shard paths, fanout, τ, rounds."],
            ["projects/fl/p2p_topology.py", "Load YAML; NeighborGraph; allow-list check; iterate edges."],
            ["projects/fl/gossip_node.py", "GossipNode: wrap FLNode; mix_with(peer_update); no server."],
            ["projects/fl/p2p_transport.py", "Transport ABC: InProcessTransport, later TcpTransport."],
            ["experiments/federated_learning/run_p2p.py", "Harness: shards, rounds, probe eval, JSON out. Must not import FederatedServer."],
            ["tests/test_p2p_gossip_mix.py", "Unit tests for size-weighted mix and reject rules."],
        ],
    )
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "Implement size_weighted_pair_mix(w_self, n_self, w_peer, n_peer) layer-wise like federated_averaging but for two parties only.",
            "GossipNode.step(round): train_local → for each sampled neighbor: transport.exchange() → mix if accepted.",
            "InProcessTransport: dict of queues; exchange is blocking within the harness barrier.",
            "run_p2p.py --transport inprocess --iid true --seed 42 writes results/p2p/p2p_inprocess_seed42.json with the same schema as baseline.",
            "Grep gate in CI or a test: run_p2p.py source must not contain FederatedServer or SimpleFLServer.",
        ],
        numbered=True,
    )
    example_box(
        doc,
        "Unit test numbers (copy into test_p2p_gossip_mix.py)",
        [
            "w_a = [np.array([1.0, 1.0])], n_a = 3",
            "w_b = [np.array([0.0, 0.0])], n_b = 1",
            "mixed = size_weighted_pair_mix(w_a, n_a, w_b, n_b)",
            "assert np.allclose(mixed[0], [0.75, 0.75])",
            "reject if peer.org_id not in neighbors → NACK untrusted",
            "reject if abs(round_a-round_b)>2 → NACK round_skew",
        ],
    )
    expected(
        doc,
        [
            "pytest tests/test_p2p_gossip_mix.py passes.",
            "python experiments/federated_learning/run_p2p.py --transport inprocess completes 20 rounds for 5 orgs.",
            "JSON has per-org F1 and probe F1. Probe F1 is within ~5 points of the FedAvg baseline on IID (or the gap is written in results/p2p/NOTES.md with the plot).",
            "rg FederatedServer experiments/federated_learning/run_p2p.py returns no matches.",
        ],
    )

    # Phase 2
    add_heading_styled(doc, "Phase 2 — Shared data shards (real-world non-IID)", 2)
    add_para(
        doc,
        "Goal. Organizations do not all see the same attacks. A bank sees more Web/Syn; an ISP sees more volumetric UDP. "
        "Shards must be files on disk so process-per-org and Mininet can load them without a parent Python object handing over arrays.",
    )
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "scripts/data/make_p2p_shards.py: read the same CIC pipeline as run_standard.py; write data/p2p_shards/org_*.npz plus data/p2p_shards/test.npz and a manifest.json (counts per class per org).",
            "IID mode: random permutation split (seed 42).",
            "Non-IID mode: primary-class assignment like run_standard.py (80% primary, 20% mix). This is the realistic SOC case.",
            "Both FedAvg and P2P load these .npz files. Stop splitting inside each experiment after this phase.",
        ],
        numbered=True,
    )
    example_box(
        doc,
        "manifest.json (illustrative counts)",
        [
            '{ "seed": 42, "mode": "non_iid",',
            '  "org_bank":  {"Syn": 4100, "WebDDoS": 1800, "Benign": 900, "n": 11200},',
            '  "org_isp":   {"DrDoS_UDP": 5200, "TFTP": 2100, "Benign": 800, "n": 14800},',
            '  "test": {"n": 8000, "shared": true} }',
        ],
    )
    expected(
        doc,
        [
            "Five train npz + one test npz. FedAvg node_1 loads the same file as org_campus.",
            "Re-run Phase 0 and Phase 1 on these files so comparison is exact.",
            "Class histogram plot saved to results/p2p/shard_histograms.png (proves Non-IID is real).",
        ],
    )

    # Phase 3
    add_heading_styled(doc, "Phase 3 — Process-per-organization on one machine (real sockets)", 2)
    add_para(
        doc,
        "Goal. This is the first “it would work in the real world” milestone: five OS processes, five listen ports, "
        "no shared RAM, crash of one process does not kill the others. Same algorithm as Phase 1.",
    )
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "Implement TcpTransport in p2p_transport.py using the existing send_msg/recv_msg (4-byte length + pickle). Bind 127.0.0.1:9101–9105.",
            "projects/fl/run_gossip_org.py --org org_isp --config config/p2p_topology.yaml. One process = one org. Loads only its npz.",
            "HELLO on connect; HEARTBEAT every 5 s; 15 s timeout; skip dead neighbor.",
            "scripts/p2p/start_five_orgs.ps1 (Windows) and start_five_orgs.sh (WSL): launch 5 processes, wait for 20 rounds, tear down.",
            "Kill org_gov at round 10 (taskkill / PID). Remaining orgs must finish. Log skipped_peers.",
        ],
        numbered=True,
    )
    example_box(
        doc,
        "Operator view (what you actually type)",
        [
            "# terminal 1",
            "python projects/fl/run_gossip_org.py --org org_campus --config config/p2p_topology.yaml",
            "# terminal 2",
            "python projects/fl/run_gossip_org.py --org org_isp --config config/p2p_topology.yaml",
            "# … three more terminals",
            "# or: powershell -File scripts/p2p/start_five_orgs.ps1",
            "# expected log line:",
            "org_isp round=7 mix=org_campus,org_bank f1=0.91 skipped=[] bytes=12.4MB",
        ],
    )
    expected(
        doc,
        [
            "Five Python processes visible in Task Manager / ps. netstat shows LISTEN on 9101–9105.",
            "Wireshark on loopback (optional) shows TCP payloads between those ports — not a single server:8888 hub.",
            "results/p2p/p2p_tcp_seed42.json matches in-process F1 within ~1–2 points (same seed, same shards).",
            "Crash test: 4/5 finish; JSON field partition.killed = [\"org_gov\"]; probe F1 of survivors recorded.",
            "No process imports FederatedServer.",
        ],
    )

    # Phase 4
    add_heading_styled(doc, "Phase 4 — Comparison pack + Byzantine neighbors", 2)
    add_para(
        doc,
        "Goal. The deliverable people will read: one table, two plots, honest limitations. "
        "Also show what happens when a partner SOC is compromised — the real reason you do not mix blindly.",
    )
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "experiments/federated_learning/run_p2p_compare.py: load baseline_fedavg + p2p json for seeds 42–44, IID and Non-IID; write results/p2p/comparison.md and comparison.json.",
            "Plot 1: macro-F1 vs round, FedAvg vs P2P probe (mean±std band).",
            "Plot 2: FPR vs round.",
            "Plot 3: MB per org per round (bar).",
            "Byzantine: mark org_cloud as malicious using existing attack_suite / byzantine_defense (sign-flip or scaled weights). Three rows: unverified gossip, gossip + Krum on neighbor set (k=1 of 2), FedAvg+Krum (existing server path).",
            "Neighbor Krum: GossipNode collects this-round neighbor updates, runs ByzantineRobustAggregator on that small set, then mixes with the selected one. If fanout=2, Krum of 2 is weak — document that; optional extra random peer from the ring to make |S|=3.",
        ],
        numbered=True,
    )
    example_box(
        doc,
        "comparison.json final table (illustrative, not claimed numbers)",
        [
            "mode              iid_F1   noniid_F1   FPR    MB/round   notes",
            "FedAvg            0.96     0.93        0.02   18         baseline kept",
            "P2P unverified    0.93     0.88        0.04   24         2 extra mix rounds needed",
            "P2P+neigh Krum    0.92     0.87        0.03   24         under 20% malicious",
            "FedAvg+Krum       0.94     0.90        0.02   18         still best under attack",
            "If P2P iid_F1 is 0.70, that is a bug — do not write the paper yet; debug mix/shards.",
        ],
    )
    expected(
        doc,
        [
            "results/p2p/comparison.json + .md + three PNG plots.",
            "Written sentence: “On honest IID data, gossip probe F1 is X vs FedAvg Y (gap Z).”",
            "Written sentence: “Unverified gossip is worse under a scaled-weight attacker than FedAvg+Krum; neighbor Krum recovers to …”",
            "If gap > 5 F1 on honest IID: either fix (push-sum v2, more mix steps per round) or explain (not enough mixing diameter). Do not tune test set.",
        ],
    )

    # Phase 5
    add_heading_styled(doc, "Phase 5 — Mininet overlay (network-real) + optional TLS", 2)
    add_para(
        doc,
        "Goal. Weights travel as packets on an emulated WAN, not just localhost. "
        "This is the demo you can Wireshark. Ryu/SDN stays a different plane — do not make the controller the FL mixer.",
    )
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "experiments/mininet/topology_p2p_orgs.py: 5 hosts h1–h5 (orgs), no h_server aggregator. Optional sixth host h_victim for later SDN. Links 100 Mbps, 10 ms delay to mimic inter-org WAN.",
            "Each host runs run_gossip_org.py with host/port from Mininet IPs (10.0.0.1–5). Reuse TcpTransport.",
            "Capture gossip TCP in Wireshark; confirm there is no single node receiving all five updates.",
            "Optional TLS: wrap sockets with ssl.SSLContext, org certs in config/p2p_certs/ (mkcert or openssl). HELLO checks cert CN == org_id.",
            "Keep existing mininet_server.py / star FedAvg demo intact for the baseline network capture.",
        ],
        numbered=True,
    )
    example_box(
        doc,
        "What “works in the real world” looks like on Mininet",
        [
            "h1 (org_campus) 10.0.0.1:9101  <-->  h2 10.0.0.2:9101  (TCP gossip)",
            "h2 <--> h3, h3 <--> h4, h4 <--> h5, h5 <--> h1",
            "iperf between h_victim and h_attacker is a DIFFERENT flow — FL packets should be small compared to DDoS flood.",
            "ovs-ofctl is unused by FL. Mixing is application-layer. SDN only consumes the exported .keras later.",
        ],
    )
    expected(
        doc,
        [
            "Mininet CLI: five gossip processes finish 20 rounds; results copied off hosts to results/p2p/mininet_seed42.json.",
            "Packet capture screenshot or pcap path in the report: multiple pairwise TCP streams.",
            "FedAvg Mininet star capture still available for contrast (one server IP 10.0.0.254:5000).",
            "TLS optional: if enabled, plaintext pickle of weights is not visible in Wireshark (TLS records instead).",
        ],
    )

    # Phase 6
    add_heading_styled(doc, "Phase 6 — Export to SDN (gated) + audit log", 2)
    add_para(
        doc,
        "Goal. A partner can actually defend a network with the gossip-trained model — only if it is safe. "
        "Fabric stores commitments, not weights.",
    )
    add_para(doc, "Tasks", bold=True)
    add_bullets(
        doc,
        [
            "After final round, each org writes checkpoints/p2p/{org_id}_round20.keras. Harness also writes models/fl_global_model_pathb_p2p.keras from probe weights.",
            "Evaluate FPR on test.npz. If FPR ≤ 2% (or ≤ FedAvg FPR + 0.5 points), print SWITCH_OK. Else print SWITCH_BLOCKED and leave sdn_model_contract.json pointing at the central model.",
            "Optional: log {org_id, round, sha256(weights), n_samples, f1} to existing fl-audit chaincode. Never send weight tensors to Fabric.",
            "Document in results/p2p/sdn_handoff.md whether the contract was switched and why.",
        ],
        numbered=True,
    )
    expected(
        doc,
        [
            "Two model files exist: central baseline and p2p probe. Contract JSON still valid JSON with a one-line note.",
            "If SWITCH_BLOCKED, that is a successful scientific outcome (same reason Path B uses the central keras today).",
            "If SWITCH_OK, controller restart loads P2P model; live SDN status still shows detections (existing loop).",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "8. Task-level acceptance checklist (print this on the wall)", 1)
    add_table(
        doc,
        ["ID", "Task", "Example of “done”", "Artifact"],
        [
            ["T0", "Freeze FedAvg baseline", "“FedAvg e=2 r=20 F1=…” spoken from a file", "results/p2p/baseline/*.json"],
            ["T1", "Mix function + tests", "assert mix([1,1],3,[0,0],1)==[0.75,0.75]", "tests/test_p2p_gossip_mix.py"],
            ["T2", "GossipNode in-process", "5 orgs, 20 rounds, no FederatedServer import", "run_p2p.py + JSON"],
            ["T3", "Disk shards", "org_isp.npz class counts ≠ org_bank.npz", "data/p2p_shards/manifest.json"],
            ["T4", "5 processes + TCP", "netstat 9101–9105; kill one, 4 finish", "p2p_tcp_seed42.json"],
            ["T5", "Comparison pack", "One table FedAvg vs P2P IID/Non-IID", "comparison.md + plots"],
            ["T6", "Byzantine row", "Unverified gossip F1 drops; Krum row recovers some", "comparison.json attacks"],
            ["T7", "Mininet overlay", "No aggregator host; pcap shows pairwise TCP", "topology_p2p_orgs.py"],
            ["T8", "SDN handoff gate", "SWITCH_OK or SWITCH_BLOCKED with FPR number", "sdn_handoff.md"],
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "9. Failure modes you must handle (otherwise it is a toy)", 1)
    add_table(
        doc,
        ["Failure", "What a real org sees", "Required behavior"],
        [
            ["Peer down", "ISP NOC process crashed", "Timeout 15 s, skip, continue round, log skipped_peers"],
            ["Slow peer", "Bank GPU busy, mix late", "Same timeout; do not block all other neighbors"],
            ["Wrong round", "Campus still on round 4, ISP on 7", "NACK round_skew if |Δ| > 2"],
            ["Oversized payload", "Bug or attack sends 2 GB pickle", "Drop if > max_msg_bytes"],
            ["Weight explode", "Malicious scale ×1e6", "NACK size_clip if ||Δw|| > τ; Phase 4 Krum"],
            ["Unknown org", "Random host hits :9101", "Reject unless org_id in YAML allow-list"],
            ["Split brain", "Link campus—isp down", "Two clusters mix internally; F1 diverges; document it"],
            ["Non-IID drift", "Gov sees only NTP reflection", "Per-org F1 on shared test; worst-org column"],
            ["Mitigation drift (later)", "After SDN drop, local data all benign", "Out of v1 scope; do not forget in discussion"],
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "10. Engineering notes (keep the code honest)", 1)
    add_bullets(
        doc,
        [
            "GossipNode must own a FLNode (or LocalTrainer), not copy-paste training loops.",
            "Transport is an interface. GossipNode.step() must not contain socket calls — otherwise Phase 1 and Phase 3 will fork.",
            "Do not pickle Keras models; send list of numpy arrays (same as Mininet today). Consider np.savez_compressed bytes if pickle is too large.",
            "Determinism: set numpy/tf seeds per org from seed + hash(org_id).",
            "Logging: one JSON line per mix event (from, to, round, bytes, accepted, reason). This is your Wireshark-without-Wireshark.",
            "Windows: start_five_orgs.ps1 is first-class. Mininet/Ryu remains WSL. Do not block Phase 3 on Mininet.",
            "Secrets: if TLS certs are generated, put them in config/p2p_certs/ and gitignore private keys.",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "11. Suggested calendar (one engineer who already knows this repo)", 1)
    add_table(
        doc,
        ["Days", "Phase", "Exit"],
        [
            ["0.5", "Phase 0 baseline freeze", "FedAvg JSON ×3 seeds"],
            ["2", "Phase 1 in-process gossip", "run_p2p.py + unit tests + grep gate"],
            ["1", "Phase 2 shards", "npz + both experiments load them"],
            ["2", "Phase 3 TCP processes", "5 ports + crash test"],
            ["1.5", "Phase 4 compare + Byzantine", "comparison.md the faculty can read"],
            ["2", "Phase 5 Mininet (WSL)", "pcap + topology without aggregator"],
            ["0.5", "Phase 6 SDN gate", "SWITCH_OK/BLOCKED written down"],
        ],
    )
    add_para(
        doc,
        "Total ~9–10 working days to a defensible comparison. Push-sum, TLS, and Fabric commits are extras after T5 exists.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "12. Claims you are allowed to make after the gates pass", 1)
    add_para(doc, "Allowed", bold=True)
    add_bullets(
        doc,
        [
            "“We keep centralized FedAvg and add a permissioned P2P gossip path among N organizations; neither path shares raw traffic.”",
            "“P2P training does not use a parameter server; each site mixes only with listed neighbors over TCP.”",
            "“On the same shards, gossip probe F1 is … versus FedAvg …; communication is … MB/org/round.”",
            "“A crashed organization does not stop the others.”",
            "“Compromised neighbor: unverified gossip degrades; neighbor-set Krum is our defense (with the small-fanout caveat).”",
        ],
    )
    add_para(doc, "Forbidden until true", bold=True)
    add_bullets(
        doc,
        [
            "“Fully trustless / blockchain FL” — Fabric is an audit log.",
            "“Internet-scale P2P” — five permissioned orgs.",
            "“Same accuracy as centralized” — only if the number says so.",
            "“SDN uses the P2P model” — only after SWITCH_OK.",
            "“Zero-knowledge proof of averaging” — not in this plan.",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "13. One-page picture of a round", 1)
    example_box(
        doc,
        "Central FedAvg (keep)",
        [
            "org_campus, org_isp, org_bank, org_cloud, org_gov",
            "        \\       |        |         |        /",
            "                 FederatedServer.federated_averaging",
            "                         |",
            "                   same w_global to all",
        ],
    )
    example_box(
        doc,
        "P2P gossip v1 (add)",
        [
            "org_campus <--> org_isp <--> org_bank <--> org_cloud <--> org_gov --.",
            "     ^                                                         |",
            "     '---------------------------------------------------------'",
            "Each arrow: GOSSIP_PUSH / GOSSIP_PULL of weights + n_samples.",
            "No center. Probe average is computed later for the plot only.",
        ],
    )

    add_heading_styled(doc, "14. Immediate next action", 1)
    add_para(
        doc,
        "Start Phase 0 today: freeze FedAvg numbers. Then implement T1+T2 (mix function, GossipNode, run_p2p.py in-process). "
        "Do not open Mininet until those JSON files exist. The comparison is the product; the sockets make it real.",
    )

    out = OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    build()
