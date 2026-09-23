"""Automated E2E test for IITKgp + War Room + SDN gateway demo."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def probe(url: str, timeout: float = 2.0) -> tuple[bool, int, float, str]:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return True, r.status, time.time() - t0, ""
    except urllib.error.HTTPError as e:
        return False, e.code, time.time() - t0, f"HTTPError_{e.code}"
    except Exception as e:
        return False, 0, time.time() - t0, type(e).__name__


def post(url: str, data: dict | None = None) -> dict:
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main() -> int:
    results: list[tuple[str, bool]] = []
    print("=== E2E SDN Demo Test ===")

    for name, url in [
        ("IITKgp", "http://127.0.0.1:8765/__ping"),
        ("Gateway", "http://127.0.0.1:8091/"),
        ("WarRoom", "http://127.0.0.1:5050/sdn"),
    ]:
        ok, code, lat, err = probe(url)
        results.append((f"baseline_{name}", ok))
        status = "OK" if ok else "FAIL"
        print(f"[1] {name}: {status} code={code} err={err} lat={lat:.2f}s")

    print("[2] Starting direct attack on :8765...")
    attack = post("http://127.0.0.1:5050/api/sdn/attack/start", {"mode": "direct"})
    print("    ", attack.get("message", ""))
    time.sleep(4)

    fails = 0
    for i in range(5):
        ok, code, lat, err = probe("http://127.0.0.1:8765/__ping", timeout=1.5)
        if not ok:
            fails += 1
        print(f"    probe {i + 1}: ok={ok} err={err} lat={lat:.2f}s")
    results.append(("attack_hung", fails >= 3))

    print("[3] Applying SDN framework...")
    apply = post("http://127.0.0.1:5050/api/sdn/apply")
    print("    ", apply.get("message", ""))
    print("    gateway_up=", apply.get("gateway_up"), "app_live=", apply.get("app_live"))
    results.append(("apply_ok", bool(apply.get("ok"))))

    time.sleep(2)
    ok, code, lat, err = probe("http://127.0.0.1:8765/__ping")
    results.append(("app_recovered", ok))
    status = "OK" if ok else "FAIL"
    print(f"[4] App after apply: {status} code={code} err={err}")

    print("[5] Attacking via :8091 (hybrid)...")
    post("http://127.0.0.1:5050/api/sdn/attack/start", {"mode": "sdn"})
    time.sleep(8)
    ok8091, code8091, _, err8091 = probe("http://127.0.0.1:8091/", timeout=3)
    print(f"    gateway probe: ok={ok8091} code={code8091} err={err8091}")
    ok8765, code8765, _, err8765 = probe("http://127.0.0.1:8765/__ping", timeout=2)
    print(f"    app behind gateway: ok={ok8765} code={code8765} err={err8765}")
    results.append(("app_protected", ok8765))
    results.append(("gateway_responding", ok8091 or code8091 == 403))

    try:
        with open("results/sdn/block_log.json", encoding="utf-8") as f:
            log = json.load(f)
        latest = log[-1] if log else None
        print(f"[6] Block log entries: {len(log)} latest={latest}")
        results.append(("block_log", len(log) > 0))
    except OSError as e:
        print("[6] Block log read failed:", e)
        results.append(("block_log", False))

    post("http://127.0.0.1:5050/api/sdn/attack/stop")
    print("=== Summary ===")
    passed = sum(1 for _, v in results if v)
    print(f"Passed {passed}/{len(results)} checks")
    for key, value in results:
        print(f"  {'PASS' if value else 'FAIL'}: {key}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
