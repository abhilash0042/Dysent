"""Generate the ZKP + P2P + FL + SDN integration implementation plan as .docx."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Cm

OUT = (
    Path(__file__).resolve().parents[1]
    / "reports"
    / "IMPLEMENTATION_PLAN_ZKP_P2P_FL_SDN.docx"
)

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
            "Dysent-1  |  ZKP + P2P FL + merging + SDN integration plan  |  "
            "Central FedAvg kept as baseline"
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
    r = st.add_run("ZKP-Gated P2P Federated Learning for Closed-Loop SDN DDoS Defense")
    set_run_font(r, size=15, color=ACCENT)

    st2 = doc.add_paragraph()
    st2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st2.paragraph_format.space_after = Pt(12)
    r = st2.add_run(
        "How ML models, centralized FL, P2P gossip, merging, SDN, and zero-knowledge proofs "
        "fit together — with a real-world example, test cases, and expected outputs"
    )
    set_run_font(r, size=11, italic=True, color=MUTED)

    add_para(
        doc,
        "This document is the integration specification. It does not replace the P2P FL plan "
        "(IMPLEMENTATION_PLAN_P2P_FL.docx) or the Byzantine/PCMI plan. Those remain the "
        "detailed build lists. This document answers: what ZKP actually does, how a real "
        "multi-organization SOC would run it, how it plugs into code you already have, "
        "what tests to write, and what numbers prove it works.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "1. What we are building (one sentence)", 1)
    add_para(
        doc,
        "Five partner organizations each train a CNN-BiLSTM DDoS detector on private traffic, "
        "exchange model updates over a permissioned P2P overlay (no central parameter server "
        "required for the P2P path), mix only updates that pass a commitment + bound check "
        "(public clip first; later a real ZKP), then export a .keras file the existing SDN "
        "controller can load to drop or rate-limit attackers on Open vSwitch / Windows FW / "
        "nftables — without ever sharing PCAP files.",
    )
    add_para(
        doc,
        "Centralized FedAvg stays. It is the baseline. P2P + ZKP is a second, comparable path.",
        bold=True,
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "2. ZKP in simple words (read this first)", 1)
    add_para(
        doc,
        "ZKP (zero-knowledge proof) is NOT a check that federated training “ran properly.” "
        "Training quality is measured by F1 / FPR on a held-out test set. ZKP is a cryptographic "
        "receipt: “my weight update follows a published rule, and I can prove that without "
        "showing you the secret numbers.”",
    )
    add_heading_styled(doc, "2.1 Airport-bag analogy", 2)
    add_table(
        doc,
        ["Everyday thing", "In this project"],
        [
            ["Did the detector actually work?", "Test-set F1 / FPR (ML evaluation)"],
            ["Did you mix the five models fairly?", "FedAvg or gossip mix math"],
            ["Is the bag under the weight limit?", "‖Δw‖₂ ≤ τ  (update not huge)"],
            ["Did you swap bags after check-in?", "SHA-256 commit matches the update"],
            ["Prove the bag is under limit WITHOUT opening it", "Real ZKP (Tier 2)"],
            ["Open the bag and weigh it in public", "Public clipping (Tier 1) — not ZKP"],
        ],
    )
    add_heading_styled(doc, "2.2 What ZKP can and cannot prove here", 2)
    add_table(
        doc,
        ["Claim", "ZKP role", "How we actually check it"],
        [
            ["Update is too large (scale poison)", "Yes — bound on ‖Δw‖", "Clip (v1) or ZKP (v2)"],
            ["Update swapped after commit", "Yes — hash bind", "commit.py + Fabric"],
            ["Neighbor mixed a fake org", "No (need allow-list + TLS certs)", "p2p_topology.yaml + HELLO"],
            ["Org trained 2 honest epochs on real CIC data", "No — out of scope", "Cannot; zkML of BiLSTM is forbidden as a claim"],
            ["Global model is accurate", "No", "Held-out test.npz F1/FPR"],
            ["SDN should drop this IP", "Indirect — PCMI must carry commit+proof", "Ryu / SDNController verify then enforce"],
        ],
    )
    add_para(
        doc,
        "Forbidden wording: calling numpy.linalg.norm(delta) <= tau a “zero-knowledge proof.” "
        "That is public clipping. The paper and this plan must say clip until a real circuit exists.",
        italic=True,
    )

    add_heading_styled(doc, "2.3 Running example used everywhere below", 2)
    add_para(
        doc,
        "Five SOCs share a DDoS detector but not packet traces. Round 7. org_bank finishes local "
        "training. It wants org_isp to mix its update. Then both want the SDN at the victim site "
        "to drop a flood source 203.0.113.50.",
    )
    add_table(
        doc,
        ["Org", "Role this round", "Private data (never leaves site)"],
        [
            ["org_campus", "Honest peer", "Campus NetFlow slice A"],
            ["org_isp", "Honest peer; will mix bank’s update", "Access-edge DDoS slice B"],
            ["org_bank", "Honest sender of Δw (or attacker in poison tests)", "Datacenter flows slice C"],
            ["org_cloud", "Honest / later Byzantine in attack tests", "East-west + VIP floods slice D"],
            ["org_gov", "Honest peer", "IXP sample slice E"],
        ],
    )
    example_box(
        doc,
        "org_bank numbers at round 7 (illustrative)",
        [
            "Local samples n = 12,200",
            "After 2 local epochs, weight change Δw has L2-norm = 3.2",
            "Policy limit τ = 10.0  →  3.2 ≤ 10 so the update is “small enough”",
            "Commit c = SHA-256(flatten(Δw) || b'org_bank' || round=7) = a3f9…",
            "If an attacker scaled Δw by 1,000,000, norm ≈ 3,200,000 > 10 → REJECT",
            "F1 on shared test set is measured AFTER mix, not by the proof",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "3. How the existing framework is organized (keep it)", 1)
    add_para(
        doc,
        "Do not rewrite the stack. Add a thin verification layer between “I have Δw” and "
        "“I mix / I install an SDN rule.”",
    )
    add_table(
        doc,
        ["Layer", "What it already does", "Path", "What ZKP/P2P adds"],
        [
            [
                "ML model",
                "CNN-BiLSTM DDoS classifier; 10 timesteps × 40 features; 18 CIC classes",
                "projects/shared_libs/cnn_bilstm_model.py",
                "Unchanged architecture. Same builder for FedAvg and P2P.",
            ],
            [
                "Local train",
                "Train on org shard; get/set weights; delta; SHA-256 of weights",
                "projects/fl/fl_node_client.py, projects/fl_node/local_trainer.py",
                "Reuse compute_weight_delta + hash; extend hash with org_id+round.",
            ],
            [
                "Central FL merge",
                "FedAvg: w = Σ (n_k/N) w_k ; also Krum, TrimmedMean, Median",
                "projects/fl/aggregation_server.py, byzantine_defense.py",
                "KEEP as baseline. Optional: server also rejects unclipped Δw.",
            ],
            [
                "P2P FL merge",
                "Not implemented yet (gossip_node.py planned)",
                "projects/fl/gossip_node.py (new)",
                "Size-weighted pair mix with neighbors only; verify before mix.",
            ],
            [
                "Trust / robust",
                "Trust scores, Krum on a set of updates",
                "trust_manager.py, byzantine_defense.py",
                "Run Krum on neighbor set AFTER proof verify (proof ≠ robust FL).",
            ],
            [
                "Audit ledger",
                "Fabric logs accuracy/loss per node/round — not weights",
                "fabric/chaincode/fl-audit/fl-audit.go",
                "Store model_commit hash in metadata or new field. Never store Δw.",
            ],
            [
                "SDN loop",
                "telemetry → detector → policy → OVS/nftables/Windows FW",
                "projects/sdn/controller.py, detector.py, contract.py, enforcement/",
                "Gate: only SWITCH_OK model; PCMI verify before install (Ryu path).",
            ],
            [
                "Model contract",
                "JSON: keras path, scaler, thresholds (alert 0.80, block 0.90)",
                "models/sdn_model_contract.json",
                "Point at p2p .keras only if FPR gate passes. Separate artifact.",
            ],
        ],
    )

    add_heading_styled(doc, "3.1 Merge techniques — which one runs where", 2)
    add_para(
        doc,
        "“Merging” means combining several model copies into one. The math lives in aggregators. "
        "ZKP does not replace merging. ZKP only decides which updates are allowed into the merge.",
    )
    add_table(
        doc,
        ["Technique", "Where it runs today", "P2P+ZKP use"],
        [
            ["FedAvg (size-weighted mean of ALL orgs)", "FederatedServer.federated_averaging", "Baseline only. P2P runner must not call this."],
            ["Pair mix (two orgs)", "New: size_weighted_pair_mix", "P2P v1 every gossip hop."],
            ["Push-sum", "Not implemented", "P2P v2 if honest-IID F1 gap > 5 points."],
            ["Krum", "ByzantineRobustAggregator.krum", "On neighbor updates this round, after proofs pass."],
            ["TrimmedMean / Median", "byzantine_defense.py", "Optional neighbor-set mix if fanout ≥ 5."],
            ["FedProx", "extended / AdaptiveAggregator", "Out of v1 P2P+ZKP; keep in intelligent FL experiments."],
        ],
    )
    example_box(
        doc,
        "Order of operations at org_isp when org_bank sends an update",
        [
            "1. TLS/HELLO: is org_bank in allow-list? if no → drop packet",
            "2. ZKP/clip verify: is ‖Δw‖ ≤ τ and commit match? if no → NACK",
            "3. (optional) Krum among {self, bank, campus} this round",
            "4. Merge: w_isp ← (n_isp*w_isp + n_bank*w_bank) / (n_isp + n_bank)",
            "5. Log commit to Fabric; write mix event JSON",
            "Proof failed → never reach step 3–4. Krum never sees poisoned giant vectors.",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "4. End-to-end how it should work in the real world", 1)
    add_para(
        doc,
        "Real world here means: each org is a separate process (later a separate host), "
        "private shards on disk, TCP gossip on listed ports, SDN consuming a file, "
        "crash of one org does not stop others. Not: open Internet FL among strangers.",
    )
    add_heading_styled(doc, "4.1 Happy path (round 7, then a live flood)", 2)
    add_bullets(
        doc,
        [
            "Each org loads only data/p2p_shards/org_*.npz. Test set data/p2p_shards/test.npz is shared for scoring only — not for training.",
            "Each org copies the same CNN-BiLSTM architecture and last accepted local weights.",
            "org_bank trains 2 epochs. Computes Δw, commit c, clip proof {type:clip, norm:3.2, tau:10}.",
            "GOSSIP_PUSH to org_isp:9102 and org_cloud (fanout=2). Payload includes n_samples, commit, proof, weights (v1).",
            "org_isp verifies clip + recomputes hash. Accepts. Mixes size-weighted. Sends GOSSIP_PULL of its own weights.",
            "After the logical round barrier, harness (offline) averages honest org weights for the PLOT only. Training never used FederatedServer.",
            "If probe FPR ≤ 2% (or ≤ FedAvg FPR + 0.5 points), write models/fl_global_model_pathb_p2p.keras and print SWITCH_OK. Else SWITCH_BLOCKED; SDN keeps the central keras.",
            "Live traffic at the victim: SDNController.process(src_ip, 40-D features) → score 0.93 ≥ block 0.90 → backend.block(). Optional PCMI: Ryu installs OF drop only if PCMI carries last good commit + valid proof + org signature.",
        ],
        numbered=True,
    )
    add_heading_styled(doc, "4.2 Failure path (attacker or crash)", 2)
    example_box(
        doc,
        "org_cloud is compromised and sends Δw × 1e6",
        [
            "v1 clip: NACK size_clip; org_isp mix log: accepted=[] skipped=['org_cloud']",
            "v2 ZKP: proof fails (or cannot be created if prover also enforces τ); mix skipped",
            "If clip were OFF: Krum may still discard the outlier IF fanout≥3; fanout=2 is weak — document it",
            "SDN does not install a drop from a PCMI signed by org_cloud if commit is not on Fabric / not attested",
        ],
    )
    example_box(
        doc,
        "org_gov process killed at round 10",
        [
            "org_campus TCP to :9105 times out in 15 s",
            "Round continues; skipped_peers includes org_gov",
            "Four remaining orgs finish round 20",
            "JSON: partition.killed=['org_gov']; probe F1 of survivors recorded",
        ],
    )

    add_heading_styled(doc, "4.3 Two planes (do not mix them in one process)", 2)
    add_table(
        doc,
        ["Plane", "Packets / objects", "Must not do"],
        [
            ["FL/P2P plane", "Weight tensors, commits, proofs, HELLO", "Install OpenFlow rules; parse live PCAP for training in v1 demo"],
            ["SDN plane", "Flow features, alerts, mitigation actions", "Average model weights; become a parameter server"],
            ["Ledger plane", "Hashes, round, org_id, optional F1", "Store keras weights or PCAP"],
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "5. Wire protocol and PCMI object", 1)
    add_heading_styled(doc, "5.1 Gossip messages (extend P2P plan)", 2)
    add_table(
        doc,
        ["Type", "New / existing", "ZKP-related fields"],
        [
            ["HELLO / HELLO_ACK", "P2P", "org_id, cert CN, protocol_version"],
            ["GOSSIP_PUSH / PULL", "P2P + ZKP", "model_commit, update_proof, n_samples, weights|delta"],
            ["NACK", "P2P + ZKP", "hash_mismatch | size_clip | proof_failed | untrusted | round_skew"],
            ["ATTEST", "new", "Ed25519 sig over (commit, round, attester_org) for PCMI peer_sigs"],
        ],
    )
    example_box(
        doc,
        "GOSSIP_PUSH JSON (v1 clip — weights still visible)",
        [
            '{ "type": "GOSSIP_PUSH", "org_id": "org_bank", "round": 7,',
            '  "n_samples": 12200,',
            '  "model_commit": "a3f9c1…",',
            '  "update_proof": { "type": "clip", "tau": 10.0, "norm": 3.2, "ok": true },',
            '  "weights": "<pickle list of ndarray>" }',
        ],
    )
    example_box(
        doc,
        "GOSSIP_PUSH (v2 ZKP — weights optional / encrypted)",
        [
            '{ "type": "GOSSIP_PUSH", "org_id": "org_bank", "round": 7,',
            '  "model_commit": "a3f9c1…",',
            '  "update_proof": { "type": "norm_zkp", "scheme": "bulletproofs_v1",',
            '    "proof": "<base64>", "public_inputs": { "tau": 10.0, "commit": "a3f9c1…" },',
            '    "prove_ms": 842, "proof_bytes": 2048 } }',
            "Neighbor: verify(proof, commit, tau) → True/False. Never stub True.",
        ],
    )
    add_heading_styled(doc, "5.2 PCMI (proof-carrying mitigation intent) for SDN", 2)
    add_para(
        doc,
        "PCMI is the object the SDN/Ryu path checks before installing a flow. Same verifier "
        "library as gossip, different payload (victim IP + action, not weight tensors).",
    )
    add_table(
        doc,
        ["Field", "Example", "Checked by"],
        [
            ["victim_ip / match", "203.0.113.50 / src=that, proto=UDP", "OpenFlow match"],
            ["action", "drop | meter | sinkhole", "Ryu / MitigationPolicy"],
            ["confidence", "0.93", "block if ≥ 0.90 (contract)"],
            ["model_commit", "a3f9c1… (round 7 org_bank or probe)", "Fabric + gossip log"],
            ["update_proof", "clip or norm_zkp", "projects/zkp verifier"],
            ["peer_sigs", "org_isp, org_campus (2-of-3)", "pcmi_schema.verify"],
            ["issuer_id, ts, nonce", "org_isp, 2026-09-23T18:11Z, n=…", "replay window 60 s"],
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "6. Code to add (and what not to touch)", 1)
    add_table(
        doc,
        ["New file", "Job"],
        [
            ["projects/zkp/commit.py", "Canonical flatten Δw + SHA-256(Δw || org_id || round)"],
            ["projects/zkp/clip.py", "L2 norm; check_clip(delta, tau) → {type, norm, ok}"],
            ["projects/zkp/norm_proof.py", "Protocol: prove/verify. ClipProofProvider then BulletproofNormProvider"],
            ["projects/zkp/merkle.py", "Chunk Δw for v2 circuit; Merkle root as commit"],
            ["projects/pcmi/pcmi_schema.py", "Dataclass, canonicalize, Ed25519 sign/verify"],
            ["projects/pcmi/verifier.py", "verify_update_proof() + verify_pcmi() one entry"],
            ["projects/fl/gossip_node.py", "Train, exchange, VERIFY, then mix (from P2P plan)"],
            ["projects/fl/p2p_transport.py", "InProcess + TCP; no sockets inside GossipNode.step"],
            ["experiments/federated_learning/run_p2p.py", "No FederatedServer import"],
            ["experiments/pcmi/run_zkp_ablation.py", "unverified | clip | zkp | clip+Krum"],
            ["tests/test_zkp_commit_clip.py", "Unit tests in §7"],
            ["tests/test_pcmi_verify.py", "Fake PCMI must fail"],
            ["tests/test_p2p_gossip_mix.py", "Pair-mix math + NACK reasons"],
        ],
    )
    add_para(doc, "Do not modify (except tiny hooks)", bold=True)
    add_bullets(
        doc,
        [
            "projects/fl/aggregation_server.py — keep FedAvg baseline.",
            "projects/shared_libs/cnn_bilstm_model.py — same model.",
            "projects/sdn/detector.py / policy.py — thresholds stay in contract JSON.",
            "SDNController: optional extra check that PCMI verified; do not put ZKP math in the controller.",
        ],
    )
    add_para(doc, "Tiny hooks (allowed)", bold=True)
    add_bullets(
        doc,
        [
            "LocalTrainer.compute_model_hash → optionally call zkp.commit.commit_delta.",
            "GossipNode.step → verifier.verify before mix.",
            "Fabric LogModelUpdate metadata JSON includes model_commit.",
            "After P2P run, write models/fl_global_model_pathb_p2p.keras; contract switch only on SWITCH_OK.",
            "SDNController.process may attach last_commit to block_log for audit.",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "7. Implementation phases (build order)", 1)
    add_para(
        doc,
        "Do not start Bulletproofs until clip ablation JSON exists. Do not switch SDN until FPR gate. "
        "Do not claim ZKP until verify() runs a real proof.",
    )

    add_heading_styled(doc, "Phase A — Freeze ML + central FL baseline", 2)
    add_para(doc, "Goal. Same shards, same CNN-BiLSTM, dated FedAvg numbers.", bold=True)
    add_bullets(
        doc,
        [
            "Reuse fl_config.yaml model: timesteps=10, 40 ensemble features, 18 classes.",
            "Write data/p2p_shards/*.npz (IID and non-IID) shared by FedAvg and P2P.",
            "Run run_standard.py seeds 42,43,44; save results/p2p/baseline/fedavg_*.json.",
        ],
        numbered=True,
    )
    expected(
        doc,
        [
            "One sentence you can say: “FedAvg e=2 r=20 seed=42 macro-F1=X FPR=Y.”",
            "SDN still points at fl_global_model_pathb_central.keras.",
        ],
    )

    add_heading_styled(doc, "Phase B — P2P gossip without proofs", 2)
    add_para(doc, "Goal. Neighbor mix works. Grep gate: no FederatedServer in run_p2p.py.", bold=True)
    add_para(
        doc,
        "Follow IMPLEMENTATION_PLAN_P2P_FL.docx Phases 1–3 (in-process, then 5 TCP processes). "
        "ZKP files may exist as no-op verify=always-accept only in a DEV flag; default production "
        "path must not ship always-accept.",
    )
    expected(
        doc,
        [
            "p2p_inprocess_seed42.json and p2p_tcp_seed42.json exist.",
            "Probe F1 within 5 points of FedAvg on honest IID, or NOTES.md explains the gap.",
        ],
    )

    add_heading_styled(doc, "Phase C — Tier 0 commit + Tier 1 public clip (required before any ZKP claim)", 2)
    add_para(doc, "Goal. Scale-poison updates never mix. Hashes land on Fabric metadata.", bold=True)
    add_bullets(
        doc,
        [
            "Implement commit.py + clip.py. τ in config/p2p_topology.yaml (start τ from 10× median honest Δw on a dry run).",
            "Gossip NACK size_clip and hash_mismatch.",
            "Fabric: put {\"model_commit\":\"a3f9…\"} in Metadata; do not add weight bytes.",
        ],
        numbered=True,
    )
    expected(
        doc,
        [
            "pytest tests/test_zkp_commit_clip.py green.",
            "Ablation row: unverified gossip F1 collapses under scale×1e6; clip row stays near honest F1.",
            "Reports say “public clipping”, not “ZKP”.",
        ],
    )

    add_heading_styled(doc, "Phase D — PCMI + SDN gate", 2)
    add_para(doc, "Goal. Mitigation install requires schema + sig + commit + clip/proof.", bold=True)
    add_bullets(
        doc,
        [
            "pcmi_schema.py + verifier.py. Ed25519 keys in config/p2p_certs/ (gitignore private keys).",
            "Fake PCMI (bad sig or unknown commit) → 0 enforcement actions in the test harness.",
            "SDN FPR gate: SWITCH_OK / SWITCH_BLOCKED in results/p2p/sdn_handoff.md.",
            "Keep current closed loop working if PCMI is absent (backward compatible flag PCMI_REQUIRED=false for lab, true for demo).",
        ],
        numbered=True,
    )
    expected(
        doc,
        [
            "test_pcmi_verify.py: valid PCMI True; tampered sig False; missing commit False.",
            "Live controller still blocks using existing detector when PCMI_REQUIRED=false.",
            "When true, backend.block is not called for forged intents.",
        ],
    )

    add_heading_styled(doc, "Phase E — Tier 2 real ZKP (optional, distinctive)", 2)
    add_para(
        doc,
        "Goal. Prove ∃ Δw : H(Δw,org,round)=c ∧ ‖Δw‖₂≤τ without revealing Δw. Report prove/verify ms and proof bytes. "
        "Chunk CNN-BiLSTM parameters (e.g. 4096 floats) via merkle.py. Bulletproofs or circom+snarkjs. "
        "If this phase slips, the paper ships clip+Krum+P2P+SDN and says so.",
        bold=False,
    )
    expected(
        doc,
        [
            "verify() false on a random proof blob; true on a proof produced by prove() for a clipped Δw.",
            "results/pcmi/zkp_timing.json: prove_ms, verify_ms, proof_bytes vs parameter count.",
            "No verify() → return True stub in committed code.",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "8. Worked example (numbers you can implement as a fixture)", 1)
    add_para(
        doc,
        "Use tiny 1-layer vectors in unit tests so you do not need the full Keras model. "
        "Production uses full CNN-BiLSTM tensors with the same functions.",
    )
    add_heading_styled(doc, "8.1 Honest mix after clip", 2)
    example_box(
        doc,
        "Inputs",
        [
            "org_isp:  w = [0.80, 0.80], n = 10_000,  (already local-trained)",
            "org_bank: w = [0.20, 0.20], n =  2_000,  Δw from previous = [0.01, 0.01]",
            "‖Δw‖₂ = sqrt(0.01²+0.01²) ≈ 0.0141  ≤  τ=10  → clip OK",
            "commit_bank = sha256(float32([0.01,0.01]) || org_bank || 7)",
        ],
    )
    example_box(
        doc,
        "isp after accepting bank",
        [
            "w' = (10000*[0.80,0.80] + 2000*[0.20,0.20]) / 12000 = [0.70, 0.70]",
            "Naive (w+w_j)/2 would be [0.50, 0.50] — WRONG; tests must fail that.",
            "Fabric metadata: org_bank R7 commit=…",
            "Mix log: accepted=['org_bank'] bytes>0 skipped=[]",
        ],
    )
    add_heading_styled(doc, "8.2 Scale poison blocked", 2)
    example_box(
        doc,
        "Attack",
        [
            "org_cloud sends w_poison = 1e6 * honest_delta  →  ‖Δw‖ ≈ huge",
            "check_clip → ok=False → NACK size_clip",
            "org_isp weights UNCHANGED this hop",
            "Expected test: np.allclose(w_after, w_before)",
        ],
    )
    add_heading_styled(doc, "8.3 SDN after SWITCH_OK", 2)
    example_box(
        doc,
        "Live packet window",
        [
            "40 CIC features, scaled with contract mean_40/scale_40",
            "SDNDetector window of 10 steps → softmax; attack_score = 1 - p(Benign)",
            "score=0.93, pps=800 → policy BLOCK (block=0.90, pps=500)",
            "If PCMI_REQUIRED: must include model_commit of last accepted round",
            "enforcement/ovs.py or windows/nftables installs drop",
            "block_log.json gains a row with source_ip and commit excerpt",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "9. Test cases and expected output", 1)
    add_para(
        doc,
        "Every test has: ID, what it protects, command/fixture, expected output. "
        "CI should run T1–T12 without Mininet. T13–T16 are integration / WSL.",
    )

    add_heading_styled(doc, "9.1 Unit tests (pytest, no GPU required)", 2)
    add_table(
        doc,
        ["ID", "Test", "Input", "Expected output"],
        [
            [
                "T1",
                "test_pair_mix_weighted",
                "w_a=[1,1] n=3; w_b=[0,0] n=1",
                "mixed=[0.75, 0.75]; NOT [0.5, 0.5]",
            ],
            [
                "T2",
                "test_commit_stable",
                "same Δw, org, round twice",
                "identical hex digest; float64 vs float32 mismatch FAILS unless we force float32 (we force float32)",
            ],
            [
                "T3",
                "test_commit_binds_org_and_round",
                "flip org_id or round",
                "digest changes",
            ],
            [
                "T4",
                "test_clip_accepts_small",
                "Δw ones(10)*0.1, τ=10",
                "ok True; proof.type=='clip'",
            ],
            [
                "T5",
                "test_clip_rejects_scale_poison",
                "Δw ones(10)*1e6, τ=10",
                "ok False; gossip NACK size_clip; weights unchanged",
            ],
            [
                "T6",
                "test_hash_mismatch_nack",
                "commit field ≠ sha256(payload)",
                "NACK hash_mismatch; no mix",
            ],
            [
                "T7",
                "test_unknown_org",
                "org_id=org_evil not in YAML",
                "drop at HELLO; no mix",
            ],
            [
                "T8",
                "test_round_skew",
                "sender round=3, local=7, skew_max=2",
                "NACK round_skew",
            ],
            [
                "T9",
                "test_pcmi_bad_signature",
                "valid JSON, flipped byte in sig",
                "verify_pcmi False; no backend.block in harness",
            ],
            [
                "T10",
                "test_pcmi_missing_commit",
                "action=drop, commit empty",
                "False when PCMI_REQUIRED",
            ],
            [
                "T11",
                "test_grep_no_federated_server",
                "source of run_p2p.py",
                "FederatedServer not in file",
            ],
            [
                "T12",
                "test_verify_not_stubbed",
                "ClipProofProvider vs fake ZKP provider",
                "random proof bytes → False; only prove() output → True for v2",
            ],
        ],
    )

    add_heading_styled(doc, "9.2 Integration tests", 2)
    add_table(
        doc,
        ["ID", "Scenario", "How to run", "Expected output"],
        [
            [
                "T13",
                "5-org in-process honest IID 20 rounds",
                "python experiments/federated_learning/run_p2p.py --transport inprocess --seed 42",
                "JSON with per-org F1 + probe F1; gap vs FedAvg ≤ 5 points or NOTES.md",
            ],
            [
                "T14",
                "5 TCP processes + kill org_gov round 10",
                "scripts/p2p/start_five_orgs.ps1 then taskkill",
                "4 processes exit 0; skipped_peers logged; netstat had 9101–9105",
            ],
            [
                "T15",
                "Scale poison 20% (1 of 5 orgs)",
                "run_zkp_ablation.py --attack scale",
                "unverified F1 drop; clip F1 close to honest; table in results/pcmi/",
            ],
            [
                "T16",
                "SDN handoff",
                "evaluate p2p keras on test.npz",
                "SWITCH_OK if FPR≤2% else SWITCH_BLOCKED; contract unchanged unless OK",
            ],
            [
                "T17",
                "Closed-loop block (existing SDN)",
                "controller.process high-score UDP flood features",
                "MitigationAction BLOCK; block_log.json row; optional commit field",
            ],
            [
                "T18",
                "Mininet pairwise gossip (WSL)",
                "topology_p2p_orgs.py",
                "pcap shows multiple TCP pairs; no 10.0.0.254 aggregator in P2P path",
            ],
        ],
    )

    add_heading_styled(doc, "9.3 Comparison table the faculty/demo must see", 2)
    example_box(
        doc,
        "results/pcmi/comparison_stack.json (illustrative, not claimed)",
        [
            "system                         iid_F1  FPR   scale-poison F1  SDN live",
            "Central train (no FL)          0.99    0.005  n/a              yes (today)",
            "FedAvg                         0.96    0.02   0.40 (no Krum)   SWITCH_BLOCKED historically",
            "FedAvg+Krum                    0.94    0.02   0.88             maybe",
            "P2P unverified                 0.93    0.04   0.35             no",
            "P2P+clip                       0.93    0.04   0.90             if FPR gate",
            "P2P+clip+Krum                  0.92    0.03   0.91             candidate",
            "P2P+norm_zkp+Krum              0.92    0.03   0.91 + privacy   distinctive",
            "If iid_F1 P2P is 0.70, debug mix/shards — do not demo ZKP yet.",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "10. Integration map (call graph)", 1)
    example_box(
        doc,
        "Training path (P2P)",
        [
            "run_gossip_org.py",
            "  → GossipNode.step()",
            "      → FLNode.train_local_model()            # existing",
            "      → LocalTrainer.compute_weight_delta()   # existing",
            "      → zkp.commit.commit_delta()             # new",
            "      → zkp.clip.check_clip() or norm_proof.prove()  # new",
            "      → transport.exchange(GOSSIP_PUSH)",
            "      → pcmi.verifier.verify_update_proof()   # new, before mix",
            "      → size_weighted_pair_mix()              # new",
            "      → optional ByzantineRobustAggregator.krum on neighbor set  # existing",
            "      → fabric LogModelUpdate(..., metadata={commit})  # existing client, new field",
        ],
    )
    example_box(
        doc,
        "Defense path (SDN)",
        [
            "packet/telemetry → 40 features",
            "  → SDNController.process()",
            "      → SDNDetector (keras from contract)     # existing",
            "      → MitigationPolicy (alert/block/pps)    # existing",
            "      → if PCMI_REQUIRED: verifier.verify_pcmi()",
            "      → EnforcementBackend.block/rate_limit   # ovs.py / nftables / windows",
            "      → block_log.json + live_sdn_status.json",
        ],
    )
    add_para(
        doc,
        "Centralized path stays: run_standard.py → FederatedServer.federated_averaging → "
        "same test.npz metrics. Used only in comparison JSON, never inside GossipNode.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "11. Real-world operations (how a SOC would run it)", 1)
    add_table(
        doc,
        ["Step", "Operator action", "Success looks like"],
        [
            ["1 Deploy org process", "python run_gossip_org.py --org org_isp --config config/p2p_topology.yaml", "LISTEN 10.0.1.12:9101; HELLO_ACK from neighbors"],
            ["2 Data", "Nightly export NetFlow → shard npz (site-local)", "manifest.json class counts; no files leave the site"],
            ["3 Train/gossip", "cron every N minutes or 20-round job", "mix log accepted peers; Fabric commit queryable"],
            ["4 Export model", "harness writes p2p keras if FPR gate", "SWITCH_OK printed or blocked with reason"],
            ["5 SDN", "restart controller with contract path", "detections in live_sdn_status.json; blocks in block_log.json"],
            ["6 Incident", "compromised peer detected", "NACK size_clip / proof_failed; revoke org in YAML; restart overlay"],
        ],
    )
    add_para(
        doc,
        "Certificates: each org has an Ed25519 (PCMI) and optional TLS server cert whose CN equals org_id. "
        "Revocation = remove from p2p_topology.yaml allow-list. That is permissioned PKI, not a public blockchain identity.",
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "12. Configuration knobs", 1)
    example_box(
        doc,
        "config/p2p_topology.yaml additions",
        [
            "zkp:",
            "  mode: clip          # clip | norm_zkp",
            "  tau: 10.0",
            "  max_msg_bytes: 67108864",
            "  pcmi_required: false  # true in demo once Phase D passes",
            "  fabric_commits: true",
            "sdn:",
            "  fpr_switch_max: 0.02",
            "  contract: models/sdn_model_contract.json",
            "  p2p_model_out: models/fl_global_model_pathb_p2p.keras",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "13. Claims allowed vs forbidden", 1)
    add_para(doc, "Allowed after the matching gate", bold=True)
    add_bullets(
        doc,
        [
            "Permissioned P2P FL among N orgs; raw traffic never shared.",
            "Updates mixed only if they pass clip (and ZKP if mode=norm_zkp).",
            "Central FedAvg kept; comparison table exists.",
            "SDN closed loop consumes a gated .keras via the existing contract.",
            "Fabric stores commitments, not models.",
        ],
    )
    add_para(doc, "Forbidden until true", bold=True)
    add_bullets(
        doc,
        [
            "“ZKP verifies training ran properly / honest SGD.”",
            "“numpy norm check is a zero-knowledge proof.”",
            "“Fully trustless / public P2P FL.”",
            "“SDN uses the P2P model” without SWITCH_OK.",
            "“ZKP replaces Krum.” (it does not stop stealthy backdoors)",
        ],
    )

    # ------------------------------------------------------------------
    add_heading_styled(doc, "14. Suggested calendar", 1)
    add_table(
        doc,
        ["Days", "Phase", "Exit artifact"],
        [
            ["0.5–1", "A baseline + shards", "fedavg JSON + npz"],
            ["2–3", "B P2P gossip", "run_p2p.py + grep gate"],
            ["1–2", "C commit+clip", "test_zkp_commit_clip.py + ablation row"],
            ["1–2", "D PCMI+SDN gate", "test_pcmi_verify.py + sdn_handoff.md"],
            ["optional 10–20", "E real ZKP circuit", "zkp_timing.json + non-stub verify"],
        ],
    )
    add_para(
        doc,
        "Immediate next action: implement projects/zkp/commit.py, clip.py, and tests T1–T6 "
        "against tiny vectors, then hook GossipNode when P2P Phase 1 lands. Do not start "
        "Halo2/circom until clip ablation exists.",
    )

    add_heading_styled(doc, "15. Related documents", 1)
    add_bullets(
        doc,
        [
            "reports/IMPLEMENTATION_PLAN_P2P_FL.docx — gossip topology, TCP, comparison vs FedAvg.",
            "reports/IMPLEMENTATION_PLAN_BYZANTINE_PCMI.docx — attacks, PCMI fields, ZKP tiers 0–4.",
            "models/sdn_model_contract.json — live inference contract (do not silently overwrite).",
        ],
    )

    out = OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    build()
