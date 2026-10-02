#!/usr/bin/env python3
"""Local web UI for app-explorer.

Usage: scripts/server.py [--port 8765]

Serves web/index.html on http://127.0.0.1:<port>, starts and stops runs of
scripts/explore.py, and exposes run status, reports, and screenshots.
Listens on localhost only.
"""
import argparse
import json
import mimetypes
import os
import re
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
WEB = ROOT / "web"
NAME = re.compile(r"^[A-Za-z0-9_-]+$")

current = {"proc": None, "log": None}


def scenarios():
    apps = []
    for app_dir in sorted((ROOT / "apps").iterdir()):
        if not (app_dir / "app.md").exists():
            continue
        items = []
        for path in sorted((app_dir / "scenarios").glob("*.md")):
            text = path.read_text()
            name = re.search(r"^name:\s*(.+)$", text, re.M)
            steps = re.search(r"^maxSteps:\s*(\d+)$", text, re.M)
            items.append({"id": path.stem, "name": name.group(1).strip() if name else path.stem,
                          "maxSteps": int(steps.group(1)) if steps else 50})
        apps.append({"id": app_dir.name, "scenarios": items})
    return apps


def running():
    proc = current["proc"]
    if proc is not None and proc.poll() is None:
        return True
    # A run started outside the UI, for example from the terminal.
    status = read_json(RUNS / "latest.json") or {}
    if status.get("state") in (None, "done", "failed") or not status.get("pid"):
        return False
    try:
        os.kill(status["pid"], 0)
    except OSError:
        return False
    return True


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def runs_list():
    out = []
    for path in sorted(RUNS.iterdir(), reverse=True):
        status = read_json(path / "status.json") if path.is_dir() else None
        if status:
            out.append({k: status.get(k) for k in
                        ("runDir", "app", "scenario", "state", "message", "start", "steps", "maxSteps",
                         "findings", "costUSD", "tokens")})
    return out[:50]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def file(self, path):
        if not path.is_file():
            return self.send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".md":
            ctype = "text/markdown; charset=utf-8"
        self.send(200, path.read_bytes(), ctype)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self.file(WEB / "index.html")
        if path == "/api/options":
            return self.send(200, {"apps": scenarios()})
        if path == "/api/status":
            status = read_json(RUNS / "latest.json")
            return self.send(200, {"running": running(), "status": status})
        if path == "/api/runs":
            return self.send(200, {"runs": runs_list()})
        match = re.match(r"^/runs/([A-Za-z0-9_-]+)/(report\.md|status\.json|screenshots/[A-Za-z0-9_.-]+)$", path)
        if match:
            return self.file(RUNS / match.group(1) / match.group(2))
        self.send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send(400, {"error": "invalid JSON"})

        if path == "/api/start":
            if running():
                return self.send(409, {"error": "A run is already in progress"})
            app, scenario = str(body.get("app", "")), str(body.get("scenario", ""))
            if not NAME.match(app) or not NAME.match(scenario):
                return self.send(400, {"error": "invalid app or scenario"})
            cmd = [sys.executable, str(ROOT / "scripts" / "explore.py"), app, scenario]
            if body.get("steps"):
                cmd += ["--steps", str(max(1, min(500, int(body["steps"]))))]
            if str(body.get("goal", "")).strip():
                cmd += ["--goal", str(body["goal"]).strip()]
            RUNS.mkdir(exist_ok=True)
            log = (RUNS / "server-run.log").open("w")
            current["proc"] = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            current["log"] = log
            return self.send(200, {"started": True})

        if path == "/api/stop":
            if not running():
                return self.send(409, {"error": "No run in progress"})
            proc = current["proc"]
            if proc is not None and proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
            else:
                os.kill((read_json(RUNS / "latest.json") or {})["pid"], signal.SIGTERM)
            return self.send(200, {"stopping": True})

        self.send(404, {"error": "not found"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"app-explorer UI: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
