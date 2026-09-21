"""End-to-end: direct DDoS on IITKgp + verify dashboard reflects hang."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def get(url: str, timeout: float = 2.0):
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={'Connection': 'close'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(32)
            return True, r.status, round(time.time() - t0, 3)
    except urllib.error.HTTPError as e:
        return False, e.code, round(time.time() - t0, 3)
    except Exception as e:
        return False, type(e).__name__, round(time.time() - t0, 3)


def ops():
    with urllib.request.urlopen('http://127.0.0.1:5050/api/sdn/ops', timeout=4) as r:
        return json.load(r)


def post_attack(mode: str = 'direct'):
    req = urllib.request.Request(
        'http://127.0.0.1:5050/api/sdn/attack/start',
        data=json.dumps({'mode': mode}).encode(),
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def stop_attack():
    req = urllib.request.Request(
        'http://127.0.0.1:5050/api/sdn/attack/stop',
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def main():
    print('=== BEFORE ===')
    print('8765', get('http://127.0.0.1:8765/'))
    o = ops()
    print('dashboard app_live', o.get('app_live'), 'health', o.get('status', {}).get('app_health', {}).get('status'))

    print('\n=== START DIRECT CRASH ATTACK ===')
    print(post_attack('direct'))

    print('\n=== DURING ATTACK (25s poll) ===')
    up_hits = down_hits = dash_down = 0
    for i in range(25):
        ok, code, lat = get('http://127.0.0.1:8765/', timeout=2)
        o = ops()
        live = o.get('app_live')
        h = o.get('status', {}).get('app_health', {}).get('status', '?')
        atk_run = o.get('attack', {}).get('running')
        died = o.get('status', {}).get('app_down_at_request')
        served = o.get('status', {}).get('served')
        discarded = o.get('status', {}).get('discarded')
        if ok:
            up_hits += 1
        else:
            down_hits += 1
        if not live:
            dash_down += 1
        print(
            f'  t={i+1:02d}s app={code}({lat}s) live={live} health={h} '
            f'attack={atk_run} died={died} served={served} discarded={discarded}'
        )
        time.sleep(1)

    print('\n=== SUMMARY ===')
    print(f'  app responding: {up_hits}/25')
    print(f'  app hung/failed:  {down_hits}/25')
    print(f'  dashboard not live: {dash_down}/25')

    hung = down_hits >= 15
    dash_ok = dash_down >= 10
    print(f'  HUNG PROPERLY: {hung}')
    print(f'  DASHBOARD SHOWS HANG: {dash_ok}')

    print('\n=== STOP ATTACK ===')
    print(stop_attack())
    time.sleep(3)
    print('8765 after stop', get('http://127.0.0.1:8765/', timeout=4))
    o = ops()
    print('dashboard after stop app_live', o.get('app_live'))

    if not hung:
        sys.exit(2)
    if not dash_ok:
        sys.exit(3)
    sys.exit(0)


if __name__ == '__main__':
    main()
