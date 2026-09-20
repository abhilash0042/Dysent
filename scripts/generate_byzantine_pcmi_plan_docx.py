"""Generate the Byzantine-robust FL + PCMI implementation plan as .docx."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor, Cm, Twips

OUT = Path(__file__).resolve().parents[1] / "reports" / "IMPLEMENTATION_PLAN_BYZANTINE_PCMI.docx"

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
MUTED = RGBColor(0x4A, 0x4A, 0x4A)


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


def shade_header_row(row):
    for cell in row.cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), "1F4E79")
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
        r = fp.add_run("FL-DDoS Implementation Plan — Byzantine-Robust FL and PCMI  |  Confidential research draft")
        set_run_font(r, size=8, color=RGBColor(0x88, 0x88, 0x88), italic=True)

    # Title
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_after = Pt(4)
    r = t.add_run("Implementation Plan")
    set_run_font(r, size=26, bold=True, color=NAVY)

    st = doc.add_paragraph()
    st.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st.paragraph_format.space_after = Pt(6)
    r = st.add_run(
        "Byzantine-Robust Federated Learning (Part A)\n"
        "and Proof-Carrying Mitigation Intents — PCMI (Part B)"
    )
    set_run_font(r, size=14, color=ACCENT)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = meta.add_run(
        "Project: ddos-detection-fl  ·  Dataset: CIC-DDoS2019  ·  "
        "Document type: engineering and research implementation plan"
    )
    set_run_font(r, size=10, italic=True, color=MUTED)

    add_para(
        doc,
        "This document is the working implementation plan for turning the existing "
        "federated DDoS detector into a paper-ready system. It is split into two "
        "parts that share one evaluation harness and one threat model. Part A is "
        "the higher-priority paper path: it uses code and data that already exist. "
        "Part B is the distinctive systems contribution: SDN actions, peer-to-peer "
        "FL, scoped model-update proofs, and PCMI. Part B is evaluated with the "
        "attackers defined in Part A. The two parts are not sequential papers; "
        "Part A is completed first as a milestone, then reused as the experiment "
        "layer of Part B.",
        size=11,
        space_after=12,
    )

    add_heading_styled(doc, "0. How to read this plan", 1)
    add_bullets(
        doc,
        [
            "Priority for a first paper: Part A (Byzantine-robust FL). Estimated 12–16 weeks to a draft if evaluation is honest.",
            "Priority for a distinctive / higher-ceiling paper: Part A + Part B together. Estimated 8–10 months if ZKP circuits are real; 5–6 months if v1 uses hash+clip instead of Groth16.",
            "Do not implement Part B and then “add Byzantine later.” Attackers, metrics, and baselines from Part A are required for Part B to mean anything.",
            "Do not run two full codebases in parallel. One repo, one split protocol, two result families.",
            "Data (CIC-DDoS2019) is not the bottleneck. Part A is experiment engineering. Part B is control-plane, networking, and crypto engineering.",
        ],
    )

    add_heading_styled(doc, "0.1 One-sentence research story", 2)
    add_para(
        doc,
        "Collaborating network domains train a DDoS detector without a trusted "
        "parameter server, reject poisoned updates using robust aggregation and "
        "(later) proofs, and install dataplane mitigation only when a signed, "
        "verified intent (PCMI) passes — then we measure both model F1 under "
        "Byzantine clients and leftover attack bandwidth versus collateral damage "
        "on legitimate traffic.",
    )

    add_heading_styled(doc, "0.2 Current repository baseline (what we start from)", 2)
    add_para(doc, "The plan is written against the present code, not an imaginary greenfield.")
    add_table(
        doc,
        ["Component", "Location", "Status vs this plan"],
        [
            [
                "CNN-BiLSTM detector",
                "projects/shared_libs/cnn_bilstm_model.py",
                "Keep as frozen backbone unless an ablation requires otherwise.",
            ],
            [
                "FedAvg server",
                "projects/fl/aggregation_server.py",
                "Part A: keep. Part B Phase 2: replace with gossip.",
            ],
            [
                "Krum / TrimmedMean / Median",
                "projects/shared_libs/byzantine_defense.py",
                "Exists; not wired into a full attacker-fraction sweep with paper metrics.",
            ],
            [
                "Malicious node helpers",
                "MaliciousNodeSimulator in byzantine_defense.py",
                "Label flip, Gaussian noise, scale poison, random weights. Missing: sign-flip, backdoor, fake PCMI.",
            ],
            [
                "Secure FL demo",
                "experiments/federated_learning/run_secure.py",
                "Starting point for Part A. Needs harness, seeds, Non-IID, F1/PR-AUC.",
            ],
            [
                "Trust manager",
                "projects/shared_libs/trust_manager.py",
                "Optional ablation (trust-weighted FedAvg), not the main method.",
            ],
            [
                "Mininet topology",
                "experiments/mininet/topology.py",
                "Star: s1 + h_server + clients. Often no real OpenFlow controller. Part B Phase 1 rewrites this.",
            ],
            [
                "Blockchain",
                "fabric/chaincode/fl-audit + hyperledger client",
                "Logs accuracy/loss. Part B needs hash(Δw) commitments, not metric logs.",
            ],
            [
                "HE / PQC modules",
                "homomorphic_encryption.py, post_quantum_crypto.py",
                "Out of scope for this plan. Do not treat simulation-as-crypto as ZKP.",
            ],
        ],
    )

    add_heading_styled(doc, "0.3 Shared evaluation protocol (both parts)", 2)
    add_para(
        doc,
        "Every experiment in Part A and Part B uses the same rules so numbers are comparable.",
    )
    add_bullets(
        doc,
        [
            "Dataset: CIC-DDoS2019 with an explicit sample budget (quote N rows, not “30GB” unless the full dump is used). Optional second domain later: Mininet/PCAP or UNSW-NB15.",
            "Split: time-aware or at least stratified hold-out. Never 34-sample test sets. Target: tens of thousands of test windows if compute allows; otherwise a documented subsample with class counts.",
            "Partition: IID vs Dirichlet Non-IID (α ∈ {0.1, 0.5, 1.0}). Default paper setting: Non-IID α = 0.5, 10 clients, 30–50% participation optional.",
            "Backbone: CNN-BiLSTM, fixed hyperparameters across aggregators (only aggregation / overlay / proofs change).",
            "Metrics: Precision, Recall, F1, PR-AUC, FPR, MCC, balanced accuracy. Per-class if multi-class; at minimum Benign vs Attack. Mean ± std over ≥ 3 seeds.",
            "Baselines always present: centralized CNN-BiLSTM, FedAvg (honest), majority/always-attack floor.",
            "Attacks (Part A definitions, reused in Part B): honest; label-flip; sign-flip / scaled weights; Gaussian noise; pattern backdoor; (Part B only) fake PCMI.",
            "Malicious fraction sweep: 0%, 10%, 20%, 30%, 40% of clients.",
            "Statistical test vs FedAvg: Wilcoxon or paired t on seed-level F1.",
            "Artifacts: JSON results, confusion matrices, round curves, saved split indices for reproducibility.",
        ],
    )

    add_heading_styled(doc, "0.4 Suggested new files (do not fork the repo)", 2)
    add_table(
        doc,
        ["Path", "Part", "Purpose"],
        [
            ["projects/shared_libs/attack_suite.py", "A", "First-class Byzantine clients (extends MaliciousNodeSimulator)."],
            ["projects/shared_libs/metrics_harness.py", "A+B", "F1, PR-AUC, FPR, MCC, seed aggregation, JSON dump."],
            ["experiments/federated_learning/run_byzantine_sweep.py", "A", "Main paper experiment driver."],
            ["projects/sdn/ryu_pcmi_app.py", "B1", "Ryu OpenFlow app: verify PCMI, install/expire flows."],
            ["projects/sdn/intent_api.py", "B1", "Northbound REST: POST /mitigate, DELETE /mitigate."],
            ["projects/pcmi/pcmi_schema.py", "B1/B3", "PCMI dataclass, canonicalize, sign, verify."],
            ["experiments/mininet/topology_two_domain.py", "B1", "Two-AS Mininet: victim, attacker, FL hosts, Ryu."],
            ["projects/fl/gossip_node.py", "B2", "P2P trainer/mixer; no FederatedServer."],
            ["projects/zkp/commit.py", "B3", "SHA-256 of Δw + round + node_id."],
            ["projects/zkp/norm_proof.py", "B3", "v1: public clip; v2: circuit prover/verifier."],
            ["experiments/pcmi/run_closed_loop.py", "B", "End-to-end detect → PCMI → OpenFlow → traffic metrics."],
        ],
    )

    # =====================================================================
    add_heading_styled(doc, "PART A — Byzantine-Robust Federated Learning", 1)
    add_para(
        doc,
        "Part A is the first implementation milestone and the higher-odds path "
        "to a mid-tier paper if time is limited. The scientific question is not "
        "“can CNN-BiLSTM detect CIC-DDoS2019?” That is already answered in the "
        "literature and in this repo. The question is: under a stated fraction of "
        "malicious FL clients, which aggregation rule preserves DDoS detection "
        "quality, and at what cost in honest-case F1?",
        size=11,
    )

    add_heading_styled(doc, "A.1 Idea (in depth)", 2)
    add_para(
        doc,
        "Standard FedAvg computes a data-size-weighted average of client models. "
        "If even a few clients send inverted gradients, scaled weights, or models "
        "trained on flipped labels, the global detector can collapse or acquire a "
        "backdoor (for example: never flag a particular source prefix). In a DDoS "
        "setting this is worse than in generic vision FL: a poisoned global model "
        "becomes a shared blind spot across every participating ISP-like node.",
    )
    add_para(
        doc,
        "Byzantine-robust FL replaces naive averaging with rules that assume some "
        "updates are arbitrary. Krum selects the update closest to the majority "
        "in Euclidean space (already implemented). Coordinate-wise median and "
        "trimmed mean discard extremes per weight (already implemented). Trust "
        "weighting down-weights nodes with a history of anomalous updates. None "
        "of these are new algorithms. The contribution is a rigorous, DDoS-specific "
        "evaluation: Non-IID CIC partitions, a documented attack suite, F1/FPR "
        "rather than inflated accuracy, and a clear Pareto curve of robustness "
        "versus honest performance.",
    )
    add_para(
        doc,
        "Why this is still publishable: FL-IDS papers often claim 99% accuracy "
        "with no attackers, or mention Krum in one paragraph without a malicious "
        "fraction sweep. A tight paper that shows FedAvg breaking at 20–30% "
        "attackers while Krum/Median hold F1 within a few points — and that "
        "honest Krum is slightly worse than FedAvg — is a complete story for "
        "TrustCom, IEEE Access, or Computers & Security.",
        italic=True,
    )

    add_heading_styled(doc, "A.2 Threat model", 2)
    add_bullets(
        doc,
        [
            "Setting: N honest-looking FL clients; f of them are fully Byzantine (arbitrary weights, or training on poisoned labels). f/N ∈ {0, 0.1, 0.2, 0.3, 0.4}.",
            "Attacker knowledge: white-box on the global model each round (standard FL). No access to other honest clients’ raw packets.",
            "Attacker goal (integrity): maximize global FPR, minimize attack recall, or implant a backdoor trigger so a chosen flood is classified Benign.",
            "Out of scope for Part A: breaking encryption of packets, compromising the aggregation process identity (Sybil storm beyond f), and control-plane fake SDN rules (that is Part B).",
            "Defender: sees only model updates and optional trust scores. Does not see raw flows from clients (privacy constraint of FL).",
        ],
    )

    add_heading_styled(doc, "A.3 Attack suite to implement", 2)
    add_table(
        doc,
        ["Attack", "Mechanism", "Why it matters for DDoS FL"],
        [
            [
                "Label flip",
                "Malicious client flips a fraction (e.g. 100% of local labels, or Benign↔Attack).",
                "Already sketched. Simulates a compromised sensor that trains the opposite of truth.",
            ],
            [
                "Sign flip / scaled update",
                "Send −Δw or λ·Δw with λ ≫ 1 (scale poison already exists).",
                "Breaks FedAvg with one loud client; Krum/Median should resist if f is small.",
            ],
            [
                "Gaussian / random weights",
                "Already in MaliciousNodeSimulator.",
                "Unstealthy; useful as a sanity check that robust methods reject noise.",
            ],
            [
                "Backdoor (new)",
                "Train so that a rare flow pattern (fixed IAT + packet-size bin) is always Benign; look normal on clean val.",
                "Stealthy. Median may not remove it if the backdoor is small in L2. This is the hard case.",
            ],
            [
                "Adaptive (optional)",
                "Attacker projects poison onto the honest update cone to stay close to majority.",
                "Shows limits of Krum. Optional for v1; strong for the paper if time allows.",
            ],
        ],
    )

    add_heading_styled(doc, "A.4 Defenses to compare", 2)
    add_table(
        doc,
        ["Method", "Code status", "Role in paper"],
        [
            ["FedAvg", "aggregation_server.py — complete", "Fragile baseline. Must fail visibly under poison."],
            ["Krum", "byzantine_defense.py — complete", "Primary robust baseline; needs f parameter sweep."],
            ["Trimmed mean", "complete", "Good when many clients; report trim ratio."],
            ["Coordinate median", "complete", "Strong vs sign-flip; weaker vs many small backdoors."],
            ["Trust-weighted FedAvg", "trust_manager.py", "Ablation: history + cosine to global. Not claimed as novel algorithm."],
            ["Multi-Krum (optional)", "not implemented", "If N is large (20+). Implement only if 10-client Krum is too coarse."],
        ],
    )

    add_heading_styled(doc, "A.5 Implementation work (detailed)", 2)
    add_heading_styled(doc, "A.5.1 Evaluation harness (weeks 1–3) — do this first", 3)
    add_para(
        doc,
        "This is the most important engineering in the whole project. Without it, "
        "neither Part A nor Part B produces a paper.",
    )
    add_bullets(
        doc,
        [
            "Create metrics_harness.py: given y_true, y_prob, compute the metric suite; write results/{exp}_{timestamp}.json.",
            "Fix data loading: one function that returns X_train/val/test, class counts, and a frozen RNG seed. Persist split indices.",
            "Client partitioner: IID shuffle vs Dirichlet over labels (and optionally over attack-type if multi-class).",
            "Train loop wrapper: local epochs E (start with 1–3), local batch, then return weights. Same E for all methods.",
            "Global eval each round on a held-out set that no client trains on.",
            "Stop quoting training accuracy as the headline number.",
        ],
        numbered=True,
    )

    add_heading_styled(doc, "A.5.2 Wire attackers as first-class clients (weeks 2–4)", 3)
    add_bullets(
        doc,
        [
            "Extend MaliciousNodeSimulator into attack_suite.py with a ClientRole: honest | label_flip | sign_flip | scale | gaussian | backdoor.",
            "In run_byzantine_sweep.py, pick f clients at random (seeded) and assign the attack. Honest clients unchanged.",
            "Log per-round: which node IDs were malicious, aggregator chosen, global F1, attack recall, benign FPR.",
            "Do not randomly “simulate” poison after aggregation. Poison must go through the same aggregate() call as honest weights.",
        ],
        numbered=True,
    )

    add_heading_styled(doc, "A.5.3 Plug aggregators into the server (weeks 3–5)", 3)
    add_para(
        doc,
        "SecureFLServer in run_secure.py already has an aggregation_method switch. "
        "Make FederatedServer.run_round accept method ∈ {fedavg, krum, trimmed_mean, median, trust} "
        "and call ByzantineRobustAggregator. Parameterize Krum’s f from the experiment config "
        "(do not hard-code f=1). If estimated f is wrong, that is an extra ablation "
        "(defender does not know f).",
    )

    add_heading_styled(doc, "A.5.4 Experiment matrix (weeks 5–10)", 3)
    add_table(
        doc,
        ["Factor", "Values", "Notes"],
        [
            ["Aggregator", "FedAvg, Krum, TrimmedMean, Median", "Trust-weighted as extra column if cheap."],
            ["Malicious fraction", "0, 10, 20, 30, 40%", "Primary x-axis of the paper figure."],
            ["Attack type", "label-flip, sign-flip, backdoor", "Separate figures; do not average incompatible attacks."],
            ["Data partition", "IID, Dirichlet 0.5", "Non-IID is the realistic one; IID is a control."],
            ["N clients", "10 (default), 20 (scalability appendix)", "Reuse run_secure / run_standard split logic."],
            ["Seeds", "3 (minimum), 5 if GPU allows", "Report mean ± std."],
        ],
    )
    add_para(
        doc,
        "Compute budget: keep local data per client modest (e.g. 5k–20k windows) "
        "so the full matrix finishes. Honesty about sample size is required. "
        "A completed 10-client × 5 fractions × 3 attacks × 3 seeds matrix is worth "
        "more than one 99% run on 50k rows.",
    )

    add_heading_styled(doc, "A.5.5 Figures and paper artifacts (weeks 10–12)", 3)
    add_bullets(
        doc,
        [
            "Figure 1: F1 vs malicious fraction, one line per aggregator, error bars (sign-flip).",
            "Figure 2: same for label-flip and for backdoor (may show Median failing).",
            "Figure 3: honest-case (0% malicious) F1 vs robust methods — the price of robustness.",
            "Table: PR-AUC, FPR, wall-clock per round, bytes (optional).",
            "Failure analysis: when Krum picks a malicious client (too many Byzantines).",
        ],
    )

    add_heading_styled(doc, "A.6 Week-by-week schedule (Part A)", 2)
    add_table(
        doc,
        ["Weeks", "Work", "Exit check"],
        [
            ["1–2", "Harness, splits, metrics, one honest FedAvg run with F1 on a real hold-out.", "JSON + confusion matrix, not accuracy-only logs."],
            ["3–4", "Attack suite + fraction sweep on FedAvg only.", "FedAvg F1 drops as f grows (if it does not, the attack is too weak)."],
            ["5–7", "Krum / Median / TrimmedMean on the same sweep.", "At least one plot where robust > FedAvg at f≥20%."],
            ["8–9", "Non-IID + backdoor attack + 3 seeds.", "Paper-shaped tables."],
            ["10–12", "Write Part A draft / workshop note. Freeze seeds and configs.", "Reproducible command: python experiments/federated_learning/run_byzantine_sweep.py"],
            ["13–16 (optional)", "Trust-weighted ablation, N=20, unknown-f Krum.", "Appendix, not required for first submission."],
        ],
    )

    add_heading_styled(doc, "A.7 End results of Part A", 2)
    add_para(doc, "When Part A is done, the project must have all of the following. If any item is missing, Part A is not complete.", bold=True)
    add_bullets(
        doc,
        [
            "A single entry-point experiment that sweeps aggregator × attack × malicious fraction × seed and writes machine-readable results.",
            "Headline metrics that a reviewer cannot dismiss: F1 / PR-AUC / FPR on a documented hold-out, with class counts.",
            "A figure showing FedAvg degrading under poison and at least one robust aggregator holding up (or an honest negative result if none hold — still publishable if the protocol is clean).",
            "A table of honest-case (0% attack) performance so robustness is not free.",
            "Reproducible configs (seed, N, E, batch, f, α) in the results JSON.",
            "Optional workshop/short paper draft: “Byzantine-robust federated DDoS detection on CIC-DDoS2019.”",
            "Interfaces that Part B will call: aggregate(weights, method), AttackClient, evaluate(model).",
        ],
    )
    add_para(
        doc,
        "Success criterion (numeric, adjust after a pilot): at 30% sign-flip attackers, "
        "chosen robust method keeps F1 within 3–5 points of honest FedAvg, while FedAvg "
        "drops by a large visible margin. If the drop is tiny, strengthen the attack "
        "(do not weaken the defense to invent a gap).",
        italic=True,
    )

    add_heading_styled(doc, "A.8 Risks and how to avoid fake results", 2)
    add_bullets(
        doc,
        [
            "Accuracy on attack-heavy CIC data: always report F1 and FPR; include always-predict-attack baseline.",
            "IID-only: Non-IID can look like Byzantine (honest updates disagree). That is a feature of the paper, not a bug — discuss it.",
            "Krum with wrong f: if defender sets f=0, Krum is meaningless. Report assumed f.",
            "Poison after the fact in numpy without going through training: not a valid FL attack.",
            "Test set of dozens of samples: forbidden.",
        ],
    )

    add_heading_styled(doc, "A.9 Mapping to a paper (Part A standalone)", 2)
    add_bullets(
        doc,
        [
            "Title shape: Robust aggregation for federated DDoS detection under poisoning.",
            "Contributions: (1) threat model + attack suite on CIC-DDoS FL; (2) empirical comparison; (3) Non-IID interaction with Krum.",
            "Venues: TrustCom, IEEE Access, Computers & Security, ICC workshops.",
            "Not enough for CCS/S&P: algorithms are known. Enough as Paper 1 or as Section 5 of the PCMI paper.",
        ],
    )

    # =====================================================================
    add_heading_styled(doc, "PART B — PCMI (Proof-Carrying Mitigation Intent)", 1)
    add_para(
        doc,
        "Part B is the systems contribution that makes the project stand out. "
        "PCMI is not a fourth ML model. It is a signed, checkable object that "
        "ties three mechanisms: (1) peer-to-peer federated learning without a "
        "central parameter server, (2) verification of model updates (hash "
        "commitment, then scoped ZKP of a norm bound), and (3) SDN/OpenFlow "
        "actions that change the dataplane. The SDN controller installs a drop "
        "or meter rule only if verify(PCMI) succeeds.",
    )
    add_para(
        doc,
        "Part B uses Part A’s attackers. A Byzantine peer can poison gossip "
        "and can also emit a fake PCMI (“blackhole this innocent prefix”). "
        "Robust aggregation alone does not stop the second attack. That is why "
        "PCMI is more than “Krum plus Mininet.”",
    )

    add_heading_styled(doc, "B.0 Idea (in depth)", 2)
    add_heading_styled(doc, "B.0.1 The gap in the current project", 3)
    add_para(
        doc,
        "Today the pipeline ends at a class label (Benign / Attack). Mitigation "
        "exists only as a string field (mitigation_action) on a blockchain log. "
        "Aggregation is a single FederatedServer process. Mininet uses a star "
        "topology with h_server. None of that is a closed-loop defense.",
    )
    add_heading_styled(doc, "B.0.2 PCMI as a data structure", 3)
    add_para(doc, "Canonical fields (implement exactly these in pcmi_schema.py):")
    add_table(
        doc,
        ["Field", "Meaning", "Who checks it"],
        [
            ["victim_ip / prefix", "Protected target", "Ryu match"],
            ["match", "src prefix, proto, ports", "OpenFlow match"],
            ["action", "drop | meter | sinkhole", "Ryu action"],
            ["ttl / idle_timeout", "Self-heal false positives", "Ryu expire"],
            ["confidence", "Detector score p(attack)", "Policy: drop vs meter"],
            ["collateral_est", "Overlap with likely-benign prefixes", "Choose meter if high"],
            ["model_commit", "SHA-256(Δw || round || node_id)", "Verifier + Fabric"],
            ["update_proof", "v1: clip attestation; v2: ZKP ‖Δw‖₂ ≤ τ", "Verifier before mix and before OF"],
            ["peer_sigs", "Neighbor attestations from gossip", "Quorum (e.g. 2-of-3)"],
            ["issuer_id, timestamp, nonce", "Replay protection", "Ryu + peers"],
        ],
    )
    add_para(
        doc,
        "Ryu installs an OpenFlow flow only if: schema valid, timestamp fresh, "
        "signatures verify, commitment matches the last accepted gossip update, "
        "and the proof verifies. Otherwise the intent is logged and dropped. "
        "This is the standout claim: another domain can mitigate without seeing "
        "raw packets, and cannot install a bogus blackhole without a proof.",
    )

    add_heading_styled(doc, "B.0.3 What “ZKP” means here (scope)", 3)
    add_table(
        doc,
        ["Tier", "Statement proven", "Part B phase"],
        [
            ["0 Hash commit", "H(Δw, round, node) is on the ledger / gossip log. Not ZKP.", "Phase 3 start (required)"],
            ["1 Public L2 clip", "Defender clips ‖Δw‖ ≤ τ in plaintext. Honest ablation, not ZK.", "Phase 3 v1 (allowed in first PCMI paper)"],
            ["2 Range / norm ZKP", "∃ Δw : H(Δw)=c ∧ ‖Δw‖₂ ≤ τ without revealing Δw.", "Phase 3 v2 (true ZKP; do not fake this)"],
            ["3 Aggregation proof", "Gossip mix / average over committed updates is correct.", "Optional if time"],
            ["4 Training SNARK / zkML of BiLSTM", "Honest SGD on private data.", "Out of scope"],
        ],
    )
    add_para(
        doc,
        "A Python check numpy.linalg.norm(dw) <= tau labelled as “zero-knowledge proof” "
        "is forbidden in reports and in the paper. Call it public clipping. If the "
        "circuit is not there, say so.",
        italic=True,
    )

    add_heading_styled(doc, "B.0.4 P2P FL idea", 3)
    add_para(
        doc,
        "Fully decentralized FL means there is no FederatedServer collecting all "
        "weights. Each site trains locally and mixes with neighbors (gossip: "
        "w ← (w + w_j)/2, or push-sum). Honest claim: permissioned P2P among "
        "a small number of ISP-like Mininet domains — not open Internet FL. "
        "Ryu is a network controller, not a parameter server. h_server as FL "
        "aggregator goes away; a victim host and attacker host remain for traffic.",
    )

    add_heading_styled(doc, "B.0.5 SDN idea", 3)
    add_para(
        doc,
        "Detection that does not change forwarding is incomplete. A Ryu application "
        "on OVS installs drop, meter (rate-limit), or sinkhole (span to collector). "
        "Policy: p > τ_high → drop; τ_low < p ≤ τ_high → meter; else delete leftover "
        "rules. Idle timeouts and a cool-down (hysteresis) stop pulse floods from "
        "flapping rules. Collateral-aware policy prefers meter when the match "
        "overlaps estimated benign prefixes.",
    )

    add_heading_styled(doc, "B.0.6 Extensions that belong in PCMI (not extra stacks)", 3)
    add_bullets(
        doc,
        [
            "Proof-carrying intents (the PCMI object itself).",
            "Mitigation-induced drift: after drop, local data becomes almost all benign; the model forgets the attack. Measure this. Mitigate with a small attack replay buffer or freeze-while-mitigating.",
            "Collateral-aware action (meter vs drop).",
            "Hysteresis / pulse defense (idle timeout + cool-down).",
        ],
    )
    add_para(
        doc,
        "Defer: extra LLM agents, new detectors, simulated PQC, Kubernetes, P4/Tofino, full zkML.",
    )

    add_heading_styled(doc, "B.1 Implementation phases", 2)
    add_para(
        doc,
        "Part B is strictly phased. Each phase has an end-result gate. Do not start "
        "Phase 3 circuits until Phase 1 traffic metrics exist. Do not claim P2P "
        "until FederatedServer is actually unused in the experiment script.",
    )

    # PHASE 1
    add_heading_styled(doc, "Phase 1 — SDN closed loop (highest leverage)", 2)
    add_para(doc, "Goal. Map detector output to real OpenFlow behavior and measure the network, not only F1.", bold=True)
    add_heading_styled(doc, "Phase 1 — analysis", 3)
    add_para(
        doc,
        "This phase does not require ZKP or gossip. It answers: if the existing "
        "CNN-BiLSTM (or a frozen checkpoint from Part A) says Attack, can we "
        "reduce flood goodput without killing a legitimate iperf/HTTP flow? "
        "That metric set is what SDN-DDoS papers actually review. It also "
        "forces the Mininet topology to become a two-sided network (attacker, "
        "victim, optional second domain) instead of a FL-only star.",
    )
    add_heading_styled(doc, "Phase 1 — work items", 3)
    add_bullets(
        doc,
        [
            "Install/run Ryu; OVS switches in Mininet with a real controller (not standalone, not iptables-on-host labelled as SDN).",
            "topology_two_domain.py: AS1 (clients + detector host), AS2 (victim), attacker host, links with measurable bandwidth.",
            "intent_api.py: REST POST /mitigate with victim, match, action, confidence, ttl.",
            "ryu_pcmi_app.py: translate intent → OF1.3 flow/meter; idle_timeout; DELETE on expire; log rule churn.",
            "Hook stream_processor or a replay of CIC/PCAP features to the API (can start with a scripted “attack on” signal, then wire the real model).",
            "Traffic: hping3/iperf flood + parallel legitimate TCP. Measure Gbps remaining, FCT, packet loss.",
            "Policy table: drop vs meter vs none from confidence; start without collateral_est, add it at the end of the phase.",
            "Hysteresis: after a rule expires, suppress reinstall for T_cool seconds unless confidence stays high.",
        ],
        numbered=True,
    )
    add_heading_styled(doc, "Phase 1 — end results (gate)", 3)
    add_bullets(
        doc,
        [
            "Demo: start flood → detector/API → OVS shows a new flow/meter → attack bandwidth falls; legitimate flow still completes.",
            "Numbers: MTTD (time to first rule), leftover attack throughput vs detect-only baseline, collateral % on the legitimate flow, rule install/delete count under a pulsing flood.",
            "Negative control: fake REST call without going through policy can still install in Phase 1 (no crypto yet). Document this hole; Phase 3 closes it.",
            "Code: topology + Ryu app + REST + a results JSON of traffic metrics. Screenshot or tcpdump/ovs-ofctl dump as appendix artifact.",
            "Do not proceed to calling this PCMI until Phase 3 attaches proofs. Phase 1 is “SDN mitigation from detection.”",
        ],
    )

    # PHASE 2
    add_heading_styled(doc, "Phase 2 — Fully decentralized (P2P) FL", 2)
    add_para(doc, "Goal. Remove the central parameter server. Same CNN-BiLSTM. Same Part A metrics.", bold=True)
    add_heading_styled(doc, "Phase 2 — analysis", 3)
    add_para(
        doc,
        "A central aggregator is itself a DDoS target and a trust bottleneck. "
        "Gossip averaging is slower (more mixing rounds to reach the same F1) "
        "and more fragile under partitions. That trade-off is the result. "
        "If the implementation secretly elects a leader, reviewers will notice. "
        "Neighbor filtering can reuse Part A: each node runs Krum/Median on the "
        "set of neighbor updates it received this round (local robust mix).",
    )
    add_heading_styled(doc, "Phase 2 — work items", 3)
    add_bullets(
        doc,
        [
            "gossip_node.py: local train → send weights to a neighbor (TCP overlay on Mininet hosts or in-process simulated links with explicit topology).",
            "Algorithm v1: periodic gossip pair averaging. Optional v2: push-sum if unbiased average is required.",
            "Overlay: static peer list for N=5–10 (permissioned). Log bytes/round separately from attack traffic.",
            "Crash/partition experiment: kill 1–2 nodes mid-run; show F1 impact vs FedAvg.",
            "Byzantine neighbors: reuse attack_suite.py; compare unverified gossip vs gossip+Krum on neighbor set vs old FederatedServer FedAvg/Krum.",
            "Stop using h_server as aggregator. Keep Ryu host distinct.",
        ],
        numbered=True,
    )
    add_heading_styled(doc, "Phase 2 — end results (gate)", 3)
    add_bullets(
        doc,
        [
            "Convergence plot: global/probe F1 vs round for FedAvg (central) vs gossip (P2P) on honest data. Gossip within a documented gap (e.g. ≤ 3–5 F1 points) or an explained larger gap.",
            "Robustness table: same malicious fractions as Part A, now on gossip. Unverified gossip should look worse than central Krum; gossip+Krum is the candidate method.",
            "No FederatedServer in the P2P experiment path (grep gate).",
            "Communication cost: MB per round vs central FedAvg.",
            "Written limitation: permissioned overlay, not permissionless.",
        ],
    )

    # PHASE 3
    add_heading_styled(doc, "Phase 3 — Commitments, proofs, and PCMI gating", 2)
    add_para(doc, "Goal. Make mixing and SDN installation conditional on verified updates/intents.", bold=True)
    add_heading_styled(doc, "Phase 3 — analysis", 3)
    add_para(
        doc,
        "ZKP is the slowest and most mis-claimed piece. Split v1 and v2 so the "
        "rest of PCMI can ship. v1 (public clip + hash) already stops naive scale "
        "poison and gives a named baseline. v2 (Bulletproofs/Groth16/Halo2 on a "
        "chunked L2 bound) is the crypto contribution: neighbors never see Δw but "
        "learn that it was bounded and matches the commit. HE in this repo hides "
        "updates from a server; ZKP proves properties to peers. They are different. "
        "Fabric should store commitments (hash, round, node), not accuracy floats.",
    )
    add_heading_styled(doc, "Phase 3 — work items", 3)
    add_bullets(
        doc,
        [
            "commit.py: canonical flatten of Δw, SHA-256, optional Fabric PutState.",
            "v1: reject gossip if ‖Δw‖ > τ; record as public_clip in PCMI.update_proof type=clip.",
            "pcmi_schema.py + sign (Ed25519). peer_sigs from neighbors who accepted the commit.",
            "Ryu: verify PCMI before OF install (closes the Phase 1 hole).",
            "Attack: fake PCMI (valid JSON, bad sig or no commit) must not install rules. Measure false-install rate.",
            "v2 (only if v1 metrics exist): circuit for Merkle-chunked weights + public τ; prove and verify; report proof size and verify milliseconds. Never stub verify() → True.",
            "Ablation: unverified gossip | clip | ZKP v2 | clip+Krum, all under Part A attacks.",
        ],
        numbered=True,
    )
    add_heading_styled(doc, "Phase 3 — end results (gate)", 3)
    add_bullets(
        doc,
        [
            "PCMI objects produced by a detector host, verified by Ryu, visible in logs (JSON).",
            "Fake PCMI attack: 0 (or near 0) successful OF installs; documented.",
            "Poisoning ASR (attack success rate) vs unverified gossip: clip and/or ZKP reduce scale-poison; Krum still needed for stealthy backdoors (discuss: ZKP does not replace robust FL).",
            "If v2 ships: proof size, prove time, verify time vs τ and vs parameter count. If v2 does not ship: paper must say public clipping, not ZKP.",
            "Fabric (optional but aligned): query commitment by round/node; mismatch rejects PCMI.",
        ],
    )

    # PHASE 4
    add_heading_styled(doc, "Phase 4 — PCMI extensions (drift, collateral, hysteresis)", 2)
    add_para(doc, "Goal. Defense quality under adaptive traffic and self-induced data shift.", bold=True)
    add_heading_styled(doc, "Phase 4 — analysis", 3)
    add_para(
        doc,
        "Closed-loop ML on a network has a feedback problem: successful drop "
        "removes attack packets from the training distribution. The next morphing "
        "or pulse wave looks novel; F1 on live traffic falls even if CIC hold-out "
        "F1 stayed high. Almost no FL-IDS paper measures this. Pulse floods "
        "(short bursts under idle_timeout) can also flap rules and create "
        "oscillation. These extensions are cheap once Phases 1–3 exist and are "
        "what reviewers remember together with PCMI.",
    )
    add_heading_styled(doc, "Phase 4 — work items", 3)
    add_bullets(
        doc,
        [
            "Replay buffer / freeze-while-mitigating: keep a capped set of confirmed-attack windows for local training while drop is active.",
            "Experiment: train during an ongoing mitigated flood vs freeze vs replay; plot live detection of a second wave.",
            "collateral_est from a simple prefix reputation or known-benign list; auto meter vs drop.",
            "Pulse traffic generator; measure rule churn with and without T_cool.",
            "Optional: east-west — domain B installs PCMI issued by domain A after verify (true multi-AS story).",
        ],
        numbered=True,
    )
    add_heading_styled(doc, "Phase 4 — end results (gate)", 3)
    add_bullets(
        doc,
        [
            "Figure: detection of wave-2 with vs without replay buffer (mitigation-induced drift).",
            "Table: collateral (benign goodput) drop vs meter vs naive drop-all.",
            "Table: rule churn under pulse flood with vs without hysteresis.",
            "Optional: cross-domain install of a verified PCMI without sharing packets.",
            "Part B is complete only when Phases 1–3 gates pass. Phase 4 is strongly recommended for the full paper; can be cut if time slips after 1–3.",
        ],
    )

    add_heading_styled(doc, "B.2 Combined experiment (Part A inside Part B)", 2)
    add_para(doc, "The paper that uses both parts compares these systems on the same seeds and attacks:")
    add_table(
        doc,
        ["System", "Aggregation", "Dataplane", "What it is"],
        [
            ["S0 Detect-only", "Central FedAvg", "None", "Current repo behavior."],
            ["S1 Robust central", "Krum/Median (Part A)", "None", "Part A method."],
            ["S2 SDN + central FL", "FedAvg or Krum", "Ryu, no PCMI crypto", "Phase 1."],
            ["S3 P2P unverified", "Gossip", "Optional SDN", "Fragile P2P."],
            ["S4 P2P + Krum", "Gossip + neighbor Krum", "Ryu", "Part A defense on P2P."],
            ["S5 PCMI v1", "Gossip + clip + commit + sig", "Ryu verify-or-drop", "Minimum distinctive system."],
            ["S6 PCMI v2", "S5 + real ZKP", "Ryu verify-or-drop", "Full claim if circuits exist."],
        ],
    )
    add_para(
        doc,
        "Required figures for the combined paper: (1) F1 vs f for S1,S3,S4,S5; "
        "(2) leftover attack Gbps and benign goodput for S0,S2,S5; "
        "(3) fake-PCMI install rate; (4) optional drift figure from Phase 4.",
    )

    add_heading_styled(doc, "B.3 Week-by-week schedule (Part B, after Part A harness exists)", 2)
    add_table(
        doc,
        ["Weeks (from start of B)", "Phase", "Exit"],
        [
            ["1–5", "Phase 1 SDN", "Traffic metrics + working OF rules"],
            ["5–8", "Phase 2 P2P", "Gossip vs FedAvg F1; no central server"],
            ["8–11", "Phase 3 v1 PCMI", "Signed intents; fake PCMI blocked; clip vs poison"],
            ["11–14", "Phase 4 + writing", "Drift/hysteresis; combined figures"],
            ["+6–10 extra", "Phase 3 v2 ZKP", "Only if targeting the crypto claim"],
        ],
    )
    add_para(
        doc,
        "If Part A weeks 1–12 and Part B weeks 1–14 overlap after week 4 of A "
        "(harness ready), total calendar time is about one academic term for "
        "A + B v1, not 12+14 sequential months. ZKP v2 is the item that pushes "
        "toward 8–10 months.",
    )

    add_heading_styled(doc, "B.4 End results of Part B (whole)", 2)
    add_para(doc, "Part B is complete when all of the following are true.", bold=True)
    add_bullets(
        doc,
        [
            "A detector can emit a PCMI; a controller installs OpenFlow only after verification.",
            "FL training in the PCMI experiment path is P2P (no parameter server).",
            "Byzantine clients from Part A are run against gossip and against PCMI; numbers exist.",
            "Network metrics exist (attack leftover, collateral), not only classification metrics.",
            "Claims match implementation: “ZKP” only if a circuit verifies; otherwise “authenticated clipped updates.”",
            "Limitation section written: permissioned peers, CIC-era attacks, Mininet not a backbone ISP, binary detection unless multi-class is actually evaluated.",
        ],
    )

    add_heading_styled(doc, "B.5 Risks specific to Part B", 2)
    add_bullets(
        doc,
        [
            "Calling iptables or Mininet TC “SDN.” Must be OpenFlow/OVS + controller.",
            "Stub ZKP. Instant credibility loss.",
            "Gossip that still posts to FederatedServer.",
            "Measuring only CIC F1 after adding Ryu — reviewers will ask for dataplane numbers.",
            "Scope creep: P4, LLM, HE, PQC in the same paper.",
        ],
    )

    # Combined
    add_heading_styled(doc, "3. Joint timeline and decision gates", 1)
    add_table(
        doc,
        ["Gate", "When", "If fail, do this"],
        [
            [
                "G0 Harness",
                "End of A weeks 2",
                "Do not start SDN. Fix metrics/splits first.",
            ],
            [
                "G1 FedAvg breaks",
                "End of A weeks 4",
                "Strengthen attacks. Do not tune defenses yet.",
            ],
            [
                "G2 Robust wins somewhere",
                "End of A weeks 7",
                "Part A paper is at risk; debug Krum f / Non-IID. Can still start Phase 1 SDN in parallel.",
            ],
            [
                "G3 OF works",
                "End of B Phase 1",
                "Do not start ZKP. Debug Mininet/Ryu.",
            ],
            [
                "G4 P2P converges",
                "End of B Phase 2",
                "Stay on central robust FL + SDN (S2) as a smaller paper; delay gossip.",
            ],
            [
                "G5 PCMI v1",
                "End of B Phase 3 v1",
                "Ship combined paper without the word ZKP. Add v2 as future work.",
            ],
        ],
    )

    add_heading_styled(doc, "4. Paper options after implementation", 1)
    add_table(
        doc,
        ["If you finish…", "Paper you can write", "Odds (qualitative)"],
        [
            ["Part A only", "Byzantine-robust FL-IDS on CIC-DDoS2019", "Highest finish-rate; incremental novelty"],
            ["A + B Phase 1", "Robust FL + SDN closed-loop mitigation", "Good; still no P2P/PCMI brand"],
            ["A + B Phases 1–3 v1", "P2P FL + proof-carrying (clipped) SDN intents", "Best balance of novelty and feasibility"],
            ["A + B through ZKP v2", "Full PCMI with ZK norm proofs", "Highest ceiling; finish risk"],
        ],
    )

    add_heading_styled(doc, "5. Explicit non-goals for this plan", 1)
    add_bullets(
        doc,
        [
            "New neural architectures (ViT, GNN, NAS) unless an ablation later needs a smaller model for zkML — not now.",
            "Additional LLM agents / OpenRouter orchestration as a contribution.",
            "Homomorphic aggregation and simulated post-quantum encryption.",
            "Training-time SNARKs of CNN-BiLSTM.",
            "Production Kubernetes multi-cloud.",
            "Claiming GDPR/HIPAA compliance from local data splits.",
        ],
    )

    add_heading_styled(doc, "6. Definition of done (project-level)", 1)
    add_para(
        doc,
        "The implementation program described in this document is done when: "
        "(1) Part A end-results list is satisfied; (2) at least Part B Phases 1–3 v1 "
        "end-result gates are satisfied; (3) one combined results directory can "
        "regenerate the paper figures from JSON; (4) README documents exact commands "
        "for run_byzantine_sweep.py and run_closed_loop.py; (5) every security claim "
        "in prose matches a function that actually runs (no simulation labelled as ZKP).",
    )

    add_heading_styled(doc, "7. References to existing project modules", 1)
    add_para(
        doc,
        "ByzantineRobustAggregator and MaliciousNodeSimulator: projects/shared_libs/byzantine_defense.py. "
        "FedAvg: projects/fl/aggregation_server.py. Secure demo: experiments/federated_learning/run_secure.py. "
        "Trust: projects/shared_libs/trust_manager.py. Model: projects/shared_libs/cnn_bilstm_model.py. "
        "Mininet: experiments/mininet/topology.py. Fabric audit chaincode: fabric/chaincode/fl-audit. "
        "This plan supersedes informal “99% production-ready” language in older reports for the purpose "
        "of the Byzantine + PCMI implementation track.",
    )

    add_heading_styled(doc, "8. Summary", 1)
    add_para(
        doc,
        "Part A (Byzantine-robust FL) is the paper-critical foundation: threat model, "
        "attack suite, aggregator comparison, honest metrics. End result: a reproducible "
        "F1-versus-malicious-fraction study on this codebase.",
    )
    add_para(
        doc,
        "Part B (PCMI) is the distinctive system, built in four gated phases: SDN "
        "actions, P2P gossip, commitments/proofs/PCMI verify-or-drop, then drift and "
        "hysteresis. Each phase has concrete end results. Data already in the project "
        "does not shorten Phases 1–3; those are engineering. Part A’s attackers are "
        "what make Part B scientifically comparable.",
    )
    add_para(
        doc,
        "Recommended execution: finish the Part A harness and FedAvg-breaks gate, "
        "start Phase 1 SDN in parallel, then P2P, then PCMI v1, and only then decide "
        "whether real ZKP circuits are in the first paper.",
        bold=True,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
