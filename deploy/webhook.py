#!/usr/bin/env python3
"""Tiny webhook that auto-deploys on push to main. Uses only stdlib."""

import hashlib
import hmac
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRET = os.environ["WEBHOOK_SECRET"].encode()
DEPLOY = "cd /opt/conta && git pull --ff-only && uv sync && systemctl restart conta"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/deploy":
            self._respond(404, b"not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        sig = self.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            self._respond(403, b"bad signature")
            return

        if self.headers.get("X-GitHub-Event") != "push":
            self._respond(200, b"ignored")
            return

        if json.loads(body).get("ref") != "refs/heads/main":
            self._respond(200, b"not main")
            return

        subprocess.Popen(["bash", "-c", DEPLOY])
        self._respond(200, b"deploying")

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9120), Handler).serve_forever()
