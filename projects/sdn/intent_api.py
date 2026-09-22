"""Small HTTP API used by the detector/PCMI producer to submit mitigation intents."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class IntentHandler(BaseHTTPRequestHandler):
    verifier = None
    installer = None
    def do_POST(self):
        if self.path != '/mitigate':
            self.send_error(404); return
        try:
            n = int(self.headers.get('Content-Length', '0'))
            body = json.loads(self.rfile.read(n))
            if self.verifier is None or self.installer is None:
                raise RuntimeError('intent verifier/installer not configured')
            ok, reason = self.verifier(body)
            if ok: self.installer(body)
            payload = {'accepted': ok, 'reason': reason}
            raw = json.dumps(payload).encode()
            self.send_response(200 if ok else 403); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        except Exception as e:
            self.send_error(400, str(e))
    def log_message(self, fmt, *args):
        return

def serve(verifier, installer, host='127.0.0.1', port=8081):
    IntentHandler.verifier = verifier; IntentHandler.installer = installer
    return HTTPServer((host, port), IntentHandler)
