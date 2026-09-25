"""Start one process per organization and gossip over localhost TCP.

This launcher is not a coordinator. It only starts the five organization
processes and waits for them. Each process binds its own port and trains
its own GossipNode.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORGS = ("org_campus", "org_isp", "org_bank", "org_cloud", "org_gov")
RUNNER = ROOT / "experiments" / "federated_learning" / "run_p2p.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch five TCP P2P organization processes")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=180)
    parser.add_argument("--config", default="config/p2p_fl.yaml")
    parser.add_argument("--real-smoke", action="store_true")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args(argv)
    if args.real_smoke and args.synthetic:
        raise SystemExit("Choose either --real-smoke or --synthetic, not both.")
    if not args.real_smoke and not args.synthetic:
        raise SystemExit("Pass --real-smoke or --synthetic. This launcher does not start a full run.")

    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        for org_id in ORGS:
            command = [
                sys.executable,
                str(RUNNER),
                "--transport",
                "tcp",
                "--org",
                org_id,
                "--seed",
                str(args.seed),
                "--rounds",
                str(args.rounds),
                "--epochs",
                str(args.epochs),
                "--max-samples",
                str(args.max_samples),
                "--config",
                args.config,
            ]
            if args.real_smoke:
                command.append("--real-smoke")
            if args.synthetic:
                command.append("--synthetic")
            processes.append(
                (
                    org_id,
                    subprocess.Popen(command, cwd=str(ROOT)),
                )
            )
        codes = []
        for org_id, process in processes:
            codes.append((org_id, process.wait()))
    except KeyboardInterrupt:
        for _org_id, process in processes:
            process.terminate()
        raise
    failed = [(org_id, code) for org_id, code in codes if code != 0]
    if failed:
        raise SystemExit(f"TCP organization processes failed: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
