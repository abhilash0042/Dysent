"""Verbose local server for the IITKgp KV-Cache demo.

Single-threaded on purpose: a connection flood / slowloris will stall
this process the same way a tiny public demo would, so the War Room
can show APP STOPPED SERVING.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(r'c:\projects\IITKgp_KVCache-1\web')
LOG = ROOT / 'results' / 'sdn' / 'iitkgp_access.json'
PORT = int(os.environ.get('IITKGP_PORT', '8765'))

_lines: list[dict] = []
_last_flush = 0.0


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _flush(force: bool = False):
    global _last_flush
    now = time.time()
    if not force and now - _last_flush < 0.4:
        return
    _last_flush = now
    _write(LOG, _lines[-180:])


_HB = b"""<div id="dysent-hb" style="display:none;position:fixed;inset:0;z-index:2147483647;background:rgba(20,0,0,.72);color:#fff;font:700 22px/1.4 sans-serif;text-align:center;padding:28vh 24px 0;pointer-events:auto;">IITKgp BACKEND HUNG<br><span style="font:600 14px/1.5 sans-serif;opacity:.9">The page you still see is cached JavaScript. New server requests are blocked (Slowloris).</span></div>
<script>
(function(){
  var b=document.getElementById('dysent-hb');
  function down(on){
    b.style.display = on ? 'block' : 'none';
    document.documentElement.style.filter = on ? 'grayscale(0.7)' : '';
  }
  function tick(){
    var c = new AbortController();
    var t = setTimeout(function(){ c.abort(); }, 1200);
    fetch('/__ping?t='+Date.now(),{cache:'no-store',signal:c.signal}).then(function(r){
      clearTimeout(t);
      if(!r.ok) throw 0;
      down(false);
    }).catch(function(){
      clearTimeout(t);
      down(true);
    });
  }
  tick();
  setInterval(tick, 1000);
})();
</script>
"""


class Handler(SimpleHTTPRequestHandler):
    # None = wait forever for a complete request. An 8s timeout was
    # letting Slowloris recover after each incomplete header stall.
    timeout = None
    protocol_version = 'HTTP/1.0'
    disable_nagle_algorithm = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def send_head(self):
        # Never 304 — a cached 304/disk copy is why a "new tab" still looks alive.
        if 'If-Modified-Since' in self.headers:
            del self.headers['If-Modified-Since']
        if 'If-None-Match' in self.headers:
            del self.headers['If-None-Match']
        return super().send_head()

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/__ping':
            body = b'ok'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ('/', '/index.html'):
            raw = (WEB / 'index.html').read_bytes()
            low = raw.lower()
            idx = low.rfind(b'</body>')
            if idx >= 0:
                raw = raw[:idx] + _HB + raw[idx:]
            else:
                raw = raw + _HB
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        ip = self.client_address[0]
        msg = fmt % args
        rec = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'ip': ip,
            'line': msg,
            'path': getattr(self, 'path', ''),
        }
        _lines.append(rec)
        del _lines[:-180]
        _flush()
        sys.stderr.write(f'[{time.strftime("%H:%M:%S")}] {ip}  {msg}\n')
        sys.stderr.flush()


class FragileHTTPServer(HTTPServer):
    # Tiny listen queue so extra SYNs wait behind the pinned worker.
    request_queue_size = 1
    timeout = None
    allow_reuse_address = False


def main():
    if not WEB.exists():
        raise SystemExit(f'IITKgp web folder missing: {WEB}')
    httpd = FragileHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    except OSError:
        pass
    print(f'IITKgp KV-Cache serving {WEB} on http://127.0.0.1:{PORT}', flush=True)
    print('SINGLE-THREAD + tiny backlog - a DDoS will stall this process.', flush=True)
    print('Request log -> results/sdn/iitkgp_access.json', flush=True)
    try:
        httpd.serve_forever(poll_interval=0.3)
    finally:
        _flush(force=True)


if __name__ == '__main__':
    main()
