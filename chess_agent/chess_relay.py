#!/usr/bin/env python3
"""
Localhost HTTP relay for the Reachy Chess Advisor extension.

Chrome extensions cannot fetch private-network IPs (10.x.x.x) directly due to
Chrome's Private Network Access enforcement. This relay listens on localhost:7862
and forwards /chess POST requests to the robot, bypassing that restriction.

Usage:
    python chess_agent/chess_relay.py [--robot http://reachy-mini.local:7860]
"""

import argparse
import json
import logging
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

PORT = 7862
_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Private-Network": "true",
}


def make_handler(robot_url: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.info(fmt, *args)

        def _send_cors(self, status: int, body: bytes, content_type: str = "application/json"):
            self.send_response(status)
            for k, v in _CORS.items():
                self.send_header(k, v)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._send_cors(200, b"")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            target = f"{robot_url.rstrip('/')}{self.path}"
            try:
                req = urllib.request.Request(
                    target, data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self._send_cors(resp.status, resp.read())
            except Exception as e:
                log.error("relay error: %s", e)
                self._send_cors(502, json.dumps({"error": str(e)}).encode())

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot", default="http://reachy-mini.local:7860")
    args = parser.parse_args()

    log.info("Chess relay: localhost:%d → %s", PORT, args.robot)
    HTTPServer(("127.0.0.1", PORT), make_handler(args.robot)).serve_forever()
