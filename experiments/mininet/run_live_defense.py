"""Live TCP gateway: protect a real local application.

Inbound connections from blocked IPs are closed immediately (requests discarded).
Per-source 1-second traffic is scored by the Path-B model; BLOCK installs
app-gateway + Windows Firewall (if admin) + WSL nftables (if available).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from projects.sdn.block_log import SDN_COMMAND_FILE
from projects.sdn.contract import SDNModelContract
from projects.sdn.controller import SDNController
from projects.sdn.enforcement.app_gateway import AppGatewayBackend
from projects.sdn.enforcement.composite import CompositeBackend
from projects.sdn.enforcement.nftables import NftablesBackend
from projects.sdn.enforcement.windows_fw import WindowsFirewallBackend
from projects.sdn.policy import ActionType
from projects.sdn.telemetry.live_features import LivePacket, SourceBucket, features_from_packets, _iat_us

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HOME_PAGE = b"""HTTP/1.1 200 OK\r
Content-Type: text/html; charset=utf-8\r
Connection: close\r
\r
<!doctype html><html><body style="font-family:sans-serif;background:#0d1321;color:#f1f5f9;padding:40px">
<h1>Protected application</h1>
<p>This service is behind the Dysent SDN gateway. Attack traffic is dropped.</p>
</body></html>
"""

BLOCK_PAGE = b"""HTTP/1.1 403 Forbidden\r
Content-Type: text/plain\r
Connection: close\r
\r
blocked by SDN
"""


def _peer_ip(writer: asyncio.StreamWriter) -> str:
    peer = writer.get_extra_info('peername')
    if not peer:
        return ''
    ip = peer[0]
    if ip.startswith('::ffff:'):
        ip = ip[7:]
    return ip


def build_backend() -> CompositeBackend:
    app = AppGatewayBackend()
    backends = [app]
    names = ['app_gateway']
    try:
        nft = NftablesBackend()
        backends.append(nft)
        names.append('nftables')
        logger.info('nftables backend available=%s', nft.available)
    except Exception as e:
        logger.warning('nftables backend skipped: %s', e)
    try:
        winfw = WindowsFirewallBackend()
        backends.append(winfw)
        names.append('windows_firewall')
        logger.info('Windows firewall backend available=%s', winfw.available)
    except Exception as e:
        logger.warning('Windows firewall backend skipped: %s', e)
    return CompositeBackend(backends, names)


class LiveGateway:
    def __init__(
        self,
        ctrl: SDNController,
        listen_host: str,
        listen_port: int,
        upstream: str | None,
        allowlist: set[str],
        protected_ip: str,
    ):
        self.ctrl = ctrl
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.upstream = upstream
        self.allowlist = allowlist
        self.protected_ip = protected_ip
        self.buckets: dict[str, SourceBucket] = defaultdict(SourceBucket)
        self._lock = asyncio.Lock()
        self.served = 0
        self.discarded = 0
        self.failed_upstream = 0
        self.last_prediction = None
        self.app_down_at_request = None
        self.app_down_since = None
        self.health = {'ok': True, 'latency_ms': 0, 'status': 'UP', 'fail_streak': 0}
        self.open_conns: dict[str, int] = defaultdict(int)

    def _log(self, kind: str, ip: str, detail: str = ''):
        self.ctrl.status.push_console({
            'kind': kind,
            'ip': ip,
            'detail': detail,
            'served': self.served,
            'discarded': self.discarded,
        })
        logger.info('%s %s %s', kind, ip, detail)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ip = _peer_ip(writer)
        if ip:
            self.open_conns[ip] += 1
        try:
            if ip and self.ctrl.backend.is_blocked(ip) and ip not in self.allowlist:
                self.discarded += 1
                self.ctrl.backend.record_drop(ip, packets=1)
                self._log('DROP', ip, 'blocked by SDN — request discarded')
                try:
                    writer.write(BLOCK_PAGE)
                    await writer.drain()
                except Exception:
                    pass
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                return

            first = await reader.read(65536)
            if not first:
                writer.close()
                return
            incomplete = b'\r\n\r\n' not in first
            self._note(ip, len(first), flags='PA', incomplete_http=incomplete)

            if incomplete:
                # Never pin the single-thread app with Slowloris holds.
                self.discarded += 1
                self._log('HOLD', ip, f'{len(first)}B incomplete HTTP — not forwarded to app')
                try:
                    await asyncio.wait_for(reader.read(1), timeout=25.0)
                except Exception:
                    pass
                try:
                    writer.write(BLOCK_PAGE)
                    await writer.drain()
                except Exception:
                    pass
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                return

            self.served += 1
            self._log('FWD', ip, f'{len(first)}B → {self.upstream or "builtin"}')

            if self.upstream:
                await self._proxy(ip, reader, writer, first)
            else:
                writer.write(HOME_PAGE)
                await writer.drain()
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
        except Exception as e:
            logger.debug('handler error %s: %s', ip, e)
            try:
                writer.close()
            except Exception:
                pass
        finally:
            if ip and self.open_conns[ip] > 0:
                self.open_conns[ip] -= 1

    def _note(self, ip: str, length: int, flags: str = '', incomplete_http: bool | None = None):
        if not ip:
            return
        pkt = LivePacket(
            ts=time.time(),
            src=ip,
            dst=self.protected_ip,
            length=length + 40,
            proto=6,
            flags=flags,
            header_len=40,
            payload_len=length,
        )
        self.buckets[ip].add(pkt, incomplete_http=incomplete_http)

    async def _proxy(self, ip: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, first: bytes):
        host, _, port_s = self.upstream.rpartition(':')
        host = host.strip() or '127.0.0.1'
        port = int(port_s)
        try:
            up_r, up_w = await asyncio.open_connection(host, port)
        except Exception as e:
            logger.warning('upstream %s failed: %s', self.upstream, e)
            self.failed_upstream += 1
            self._log('UPSTREAM_FAIL', ip, str(e))
            writer.close()
            return
        up_w.write(first)
        await up_w.drain()

        async def pump(src, dst, inbound: bool):
            try:
                while True:
                    data = await src.read(65536)
                    if not data:
                        break
                    if inbound:
                        if self.ctrl.backend.is_blocked(ip) and ip not in self.allowlist:
                            self.discarded += 1
                            self.ctrl.backend.record_drop(ip, packets=1)
                            break
                        self._note(ip, len(data), flags='PA')
                    dst.write(data)
                    await dst.drain()
            except Exception:
                pass
            try:
                dst.close()
            except Exception:
                pass

        await asyncio.gather(pump(reader, up_w, True), pump(up_r, writer, False))

    async def score_loop(self, interval: float):
        contract = self.ctrl.contract
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(interval)
            snapshot = dict(self.buckets)
            self.buckets = defaultdict(SourceBucket)
            for ip, bucket in snapshot.items():
                if not bucket.packets:
                    continue
                if ip in self.allowlist:
                    continue
                if self.ctrl.backend.is_blocked(ip):
                    self.ctrl.backend.record_drop(ip, packets=len(bucket.packets))
                    continue
                feat = features_from_packets(
                    bucket.packets, self.protected_ip, interval, contract,
                )
                pps = float(len(bucket.packets)) / max(interval, 1e-3)
                seen = bucket.incomplete + bucket.complete
                incomplete_ratio = (bucket.incomplete / seen) if seen else 0.0
                mean_iat, _, _, _ = _iat_us([p.ts for p in bucket.packets])
                concurrent = int(self.open_conns.get(ip, 0))
                act = await loop.run_in_executor(
                    None,
                    lambda ip=ip, feat=feat, pps=pps, incomplete_ratio=incomplete_ratio,
                    concurrent=concurrent, mean_iat=mean_iat: self.ctrl.process(
                        ip, feat, pps, features_already_scaled=False,
                        incomplete_ratio=incomplete_ratio,
                        concurrent=concurrent,
                        mean_iat_us=mean_iat,
                    ),
                )
                if act and act.action != ActionType.NONE:
                    self.last_prediction = {
                        'source_ip': act.source_ip,
                        'attack_class': act.attack_class,
                        'attack_score': round(act.attack_score, 4),
                        'pps': round(act.pps, 1),
                        'action': act.action.value,
                        'reason': act.reason,
                        'switch': self.ctrl.backend.stats().get('backend', ''),
                    }
                    self._log('PREDICT', ip, f'{act.attack_class} score={act.attack_score:.2f} → {act.action.value}')
                if act and act.action == ActionType.BLOCK:
                    logger.warning('LIVE BLOCK %s — further requests will be discarded', ip)
            extra = {
                'served': self.served,
                'discarded': self.discarded,
                'failed_upstream': self.failed_upstream,
                'last_prediction': self.last_prediction,
                'app_health': self.health,
                'app_down_at_request': self.app_down_at_request,
                'protected_app': self.upstream,
                'listen_port': self.listen_port,
            }
            await loop.run_in_executor(None, lambda: self.ctrl.flush_status(extra))

    async def health_loop(self):
        while True:
            await asyncio.sleep(1.0)
            ok, ms, err = await asyncio.get_running_loop().run_in_executor(None, self._probe_app)
            down = False
            if ok:
                self.health = {'ok': True, 'latency_ms': ms, 'status': 'UP', 'fail_streak': 0, 'error': ''}
                if self.app_down_since:
                    self._log('APP_RECOVER', '-', f'IITKgp serving again after {int(time.time()-self.app_down_since)}s')
                self.app_down_since = None
                self.app_down_at_request = None
            else:
                streak = self.health.get('fail_streak', 0) + 1
                down = streak >= 2
                self.health = {
                    'ok': not down,
                    'latency_ms': ms,
                    'status': 'DOWN' if down else 'DEGRADED',
                    'fail_streak': streak,
                    'error': err,
                }
                if down and self.app_down_since is None:
                    self.app_down_since = time.time()
                    self.app_down_at_request = self.served + self.discarded
                    self._log('APP_DOWN', '-', f'IITKgp stopped serving after {self.app_down_at_request} observed requests ({err})')
            extra = {
                'served': self.served,
                'discarded': self.discarded,
                'failed_upstream': self.failed_upstream,
                'last_prediction': self.last_prediction,
                'app_health': self.health,
                'app_down_at_request': self.app_down_at_request,
                'protected_app': self.upstream,
                'listen_port': self.listen_port,
            }
            await asyncio.get_running_loop().run_in_executor(None, lambda e=extra: self.ctrl.flush_status(e))

    async def command_loop(self):
        """Operator Apply-SDN: dashboard writes sdn_commands.json."""
        while True:
            await asyncio.sleep(0.25)
            if not SDN_COMMAND_FILE.exists():
                continue
            try:
                raw = SDN_COMMAND_FILE.read_text(encoding='utf-8')
                cmd = json.loads(raw)
            except Exception:
                continue
            try:
                SDN_COMMAND_FILE.unlink(missing_ok=True)
            except OSError:
                pass
            op = (cmd or {}).get('op')
            ip = (cmd or {}).get('ip') or '127.0.0.1'
            if op == 'block' and ip not in self.allowlist:
                meta = {
                    'attack_class': cmd.get('attack_class', 'operator_apply_sdn'),
                    'attack_score': float(cmd.get('attack_score', 0.99)),
                    'packets': 0,
                }
                self.ctrl.backend.block_ip(ip, int(cmd.get('ttl_seconds', 300)), meta)
                self.ctrl.actions_taken += 1
                rec = {
                    'source_ip': ip,
                    'attack_class': meta['attack_class'],
                    'attack_score': meta['attack_score'],
                    'reason': cmd.get('reason', 'Apply SDN framework'),
                    'switch': self.ctrl.backend.stats().get('backend', ''),
                }
                self.last_prediction = {
                    'source_ip': ip,
                    'attack_class': rec.get('attack_class'),
                    'attack_score': rec.get('attack_score'),
                    'pps': 0,
                    'action': 'block',
                    'reason': rec.get('reason'),
                    'switch': rec.get('switch'),
                }
                self._log('BLOCK', ip, rec.get('reason', 'Apply SDN'))
                extra = {
                    'served': self.served,
                    'discarded': self.discarded,
                    'failed_upstream': self.failed_upstream,
                    'last_prediction': self.last_prediction,
                    'app_health': self.health,
                    'protected_app': self.upstream,
                    'listen_port': self.listen_port,
                    'sdn_applied': True,
                }
                await asyncio.get_running_loop().run_in_executor(None, lambda: self.ctrl.flush_status(extra))
            elif op == 'revoke' and ip:
                self.ctrl.backend.revoke(ip)
                self._log('REVOKE', ip, 'operator revoke')

    def _probe_app(self):
        import urllib.request
        url = 'http://' + (self.upstream or '127.0.0.1:8765')
        if not url.endswith('/'):
            url += '/'
        t0 = time.time()
        try:
            urllib.request.urlopen(url, timeout=1.5).read(64)
            return True, int((time.time() - t0) * 1000), ''
        except Exception as e:
            return False, int((time.time() - t0) * 1000), type(e).__name__


async def _amain(args):
    contract = SDNModelContract.load()
    if args.pps_threshold is not None:
        contract.pps_threshold = float(args.pps_threshold)
    backend = build_backend()
    ctrl = SDNController(backend, contract=contract)
    logger.info('Preloading Keras model so the gateway does not stall on first attack...')
    ctrl.detector._load_model()
    allow = set(args.allow or [])
    if not args.allow_localhost_block:
        allow.update({'127.0.0.1', '::1', 'localhost'})
    host_ip = args.bind if args.bind not in ('0.0.0.0', '::') else '127.0.0.1'
    gw = LiveGateway(ctrl, args.bind, args.port, args.upstream, allow, host_ip)
    server = await asyncio.start_server(gw.handle, args.bind, args.port)
    socks = ', '.join(str(s.getsockname()) for s in server.sockets)
    logger.info('LIVE SDN gateway on %s  upstream=%s  pps_threshold=%.0f', socks, args.upstream or '(built-in app)', contract.pps_threshold)
    logger.info('Allowlist (never block): %s', sorted(allow) or '(empty)')
    logger.info('Put a real app behind this with --upstream 127.0.0.1:PORT')
    ctrl.flush_status()
    async with server:
        await asyncio.gather(
            server.serve_forever(),
            gw.score_loop(args.window_seconds),
            gw.health_loop(),
            gw.command_loop(),
        )


def main():
    p = argparse.ArgumentParser(description='Live SDN defense for a real TCP/HTTP application')
    p.add_argument('--bind', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8088)
    p.add_argument('--upstream', default='', help='host:port of the real app to protect (empty = built-in page)')
    p.add_argument('--window-seconds', type=float, default=1.0)
    p.add_argument('--pps-threshold', type=float, default=40.0, help='Events/s gate for live traffic (model still required unless volumetric)')
    p.add_argument('--allow', action='append', default=[], help='IP that must never be blocked')
    p.add_argument('--allow-localhost-block', action='store_true', help='Allow blocking 127.0.0.1 (use only for local tests)')
    args = p.parse_args()
    if not args.upstream:
        args.upstream = None
    try:
        asyncio.run(_amain(args))
    except KeyboardInterrupt:
        logger.info('stopped')


if __name__ == '__main__':
    main()
