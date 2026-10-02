#!/usr/bin/env python3
"""Run the medstime-probe bot on an iOS app, without a model as orchestrator.

Usage:
  explore.py <app> <scenario> [--steps N] [--goal "..."] [--persona "..."] [--model M] [--effort E]

The script builds and installs the app, runs the bot in segments through
`claude -p --agent medstime-probe --json-schema`, records every segment, and at
the end asks the report model once for the report summary and analysis.

--steps overrides the scenario's maxSteps. --goal replaces the scenario's goal
and turns it into an open-ended run (no "Done when"). --persona replaces the scenario's persona. --model runs the bot on
another model (for example sonnet) instead of the agent's default, Haiku.
--effort overrides the agent's effort level (low by default). A gpt-* model runs the
bot through the Codex CLI (`codex exec`) against the same MobileBuildMCP server.
--report-model picks who writes the report (Sonnet 5.5 by default), always at low effort.
A Claude model with the suffix ":no-thinking" (for example claude-sonnet-5-5:no-thinking) runs
that model without extended thinking and without --effort.

Progress is written to <run dir>/status.json and runs/latest.json for the web UI.
"""
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "scripts" / "segment_schema.json"
DERIVED_DATA = ROOT / ".build" / "DerivedData"
# Source fingerprint of the last successful build, per project, scheme, and configuration.
BUILD_FINGERPRINTS = ROOT / ".build" / "fingerprints.json"
EFFORTS = ("low", "medium")
AGENT = ROOT / ".claude" / "agents" / "medstime-probe.md"
REPORT_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5", "gpt-6-sol")
# Model suffix that runs a Claude bot without extended thinking.
NO_THINKING = ":no-thinking"
CODEX_APP_BIN = Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")
# Codex has no StructuredOutput tool; --output-schema makes the final message the result.
# --narrate: the bot announces each action in one sentence, shown in the live feed.
NARRATE_NOTE = ("Narration is on for this run, overriding \"Work silently\": before each tool call, "
                "write one short sentence saying what you are about to do and why.")
CODEX_NOTE = ("There is no StructuredOutput tool here: wherever these instructions say to call it, "
              "make your final message the JSON result itself, with nothing else around it.")
SEGMENT_STEPS = 10
MIN_SEGMENT_STEPS = 3
SEVERITY = ["crash", "bug", "ux", "minor"]
# Token counts reported by claude -p, by kind.
TOKEN_KINDS = {"input": "inputTokens", "cacheRead": "cacheReadInputTokens",
               "cacheWrite": "cacheCreationInputTokens", "output": "outputTokens"}
MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "avg", "sep", "okt", "nov", "dec"]

RULES = """Tap only with touch (down true, up true, delay 0.15); short taps are often ignored. Before typing, touch the text field and check that the keyboard appeared, then type_text, then check the field shows the text. Act on the snapshot each action returns; call wait_for_ui with predicate "settled" only when that snapshot looks mid-change (spinner, empty or half-drawn screen, sheet or alert still sliding in), never by default. Before marking a step no_effect, wait for settled and retry once; only report a control as broken if the retry also fails. Take a screenshot only when something looks wrong, while it is on screen; every finding needs one, and nothing else does. Always take a screenshot, while it is on screen, when a banner or popup drops in from the top (the purple error popup) and report it as a finding quoting its text. Use made-up names for anything you enter (for example \"Testamin 10 mg\"), never real medications or personal data. On a paywall, buy: pick a plan, tap Continue/Subscribe, and confirm the purchase sheet if one appears (with the app's mock store the purchase completes with no sheet; a sheet says \"Environment: Xcode\" or \"Environment: Sandbox\"; all are test environments, so nothing is charged). Never type a password or sign in to an Apple Account; if a sign-in prompt appears, cancel it and report a finding. Never tap Cancel Subscription or Manage Subscriptions: they open Apple's App Store sheet, which cannot load in this test setup. Always allow notifications; skip alarms (Skip or Not now, Don't Allow on the system alert). Never open the iOS Settings app and never press Home; if another app comes to the front, tap the \"◀ <app name>\" link in the top-left corner; if the snapshot does not list it, stop the segment at once with status left_app and the program brings the app back. Leaving the app is not a crash. Stay within this segment's step budget. Work silently. Finish with a real call to the StructuredOutput tool; never write the JSON as text."""

REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "analysis"],
    "properties": {
        "summary": {"type": "string"},
        "analysis": {"type": "string"},
    },
}

REPORT_PROMPT = """You review a run of an automated QA bot ({model}) that used an iOS app in the Simulator like a first-time user. Below are the run settings, the bot's segment summaries, its findings, and every step it took.

Write, in English:
- "summary": 3-5 sentences. What the bot did, where it ended, the most important problems.
- "analysis": Markdown. Use ### for section headings, never # or ##. Short sections:
  - "Findings that matter": merge duplicates; for each, say why it matters.
  - "Likely bot errors": findings or no_effect steps that look like the bot's own mistake (for example tapping during an animation, misreading the screen) rather than an app problem. Say "None" if there are none.
  - "Check first": the 1-3 things a developer should verify by hand.
Base everything on the data; do not invent screens or behavior.

{data}"""


def claude_bin():
    return shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")


def codex_bin():
    return shutil.which("codex") or str(CODEX_APP_BIN)


def is_openai(model):
    return bool(model) and model.startswith("gpt-")


def codex_mcp_config(tools):
    """-c overrides that give codex exec the project's MobileBuildMCP server, limited to tools."""
    server = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["mobilebuildmcp"]
    env = ", ".join(f"{k} = {json.dumps(v)}" for k, v in server.get("env", {}).items())
    key = "mcp_servers.mobilebuildmcp"
    return ["-c", f"{key}.command={json.dumps(server['command'])}",
            "-c", f"{key}.args={json.dumps(server.get('args', []))}",
            "-c", f"{key}.env={{{env}}}",
            "-c", f"{key}.enabled_tools={json.dumps(tools)}"]


def codex_exec(model, effort, schema_path, prompt, extra=()):
    """Start codex exec with a JSON event stream on stdout."""
    return subprocess.Popen(
        [codex_bin(), "exec", "--json", "--ignore-user-config", "--skip-git-repo-check", "-C", str(ROOT),
         "-s", "read-only", "-m", model, "-c", f"model_reasoning_effort={json.dumps(effort)}",
         "--output-schema", str(schema_path), *extra, prompt],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def codex_usage(usage):
    """Codex turn usage in the token kinds of TOKEN_KINDS."""
    cached = usage.get("cached_input_tokens", 0)
    return {"input": usage.get("input_tokens", 0) - cached, "cacheRead": cached,
            "cacheWrite": usage.get("cache_write_input_tokens", 0), "output": usage.get("output_tokens", 0)}


def codex_result(model, usage, text):
    """A claude -p style result for a codex run. Runs on a ChatGPT plan report no dollar cost."""
    return {"result": text, "total_cost_usd": 0,
            "modelUsage": {model: {"costUSD": 0, **{TOKEN_KINDS[k]: v for k, v in codex_usage(usage).items()}}}}


def now():
    return datetime.now().astimezone()


# ---------- config ----------

def parse_front_matter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        return {}, text.strip()
    meta = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if not value:
            continue
        try:
            meta[key.strip()] = json.loads(value)
        except ValueError:
            meta[key.strip()] = value
    return meta, match.group(2).strip()


def sections(body):
    return {m.group(1).strip().lower(): m.group(2).strip()
            for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", body, re.S | re.M)}


def resolve_udid(name):
    out = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "-j"],
                         check=True, capture_output=True, text=True).stdout
    best = None
    for runtime, devices in json.loads(out)["devices"].items():
        version = re.search(r"iOS-(\d+)-(\d+)", runtime)
        if not version:
            continue
        key = (int(version.group(1)), int(version.group(2)))
        for device in devices:
            if device["name"] == name and (best is None or key > best[0]):
                best = (key, device["udid"])
    if best is None:
        raise RuntimeError(f"No available simulator named {name!r}")
    return best[1]


# ---------- run state ----------

class Run:
    def __init__(self, args):
        app_path = ROOT / "apps" / args.app / "app.md"
        scenario_path = ROOT / "apps" / args.app / "scenarios" / f"{args.scenario}.md"
        if not app_path.exists() or not scenario_path.exists():
            raise SystemExit(f"Missing {app_path} or {scenario_path}")
        config, app_notes = parse_front_matter(app_path)
        meta, body = parse_front_matter(scenario_path)
        parts = sections(body)

        self.start = now()
        self.dir = ROOT / "runs" / f"{self.start:%Y-%m-%d-%H%M%S}-{args.app}-{args.scenario}"
        (self.dir / "screenshots").mkdir(parents=True)
        model, no_thinking = args.model, False
        if model and model.endswith(NO_THINKING) and not is_openai(model):
            model, no_thinking = model.removesuffix(NO_THINKING), True
        self.meta = {
            "app": args.app,
            "scenario": args.scenario,
            "appName": config.get("name", args.app),
            "scenarioName": meta.get("name", args.scenario),
            "start": self.start.isoformat(timespec="seconds"),
            "maxSteps": int(args.steps or meta.get("maxSteps", 50)),
            "model": model,
            "effort": None if no_thinking else args.effort,
            "reportModel": args.report_model,
            "narrate": args.narrate,
            "freshStart": bool(meta.get("freshStart")),
            "skipOnboarding": bool(meta.get("skipOnboarding")),
            # "off" runs the bot without extended thinking, for fast runs: a scenario preset, or a
            # ":no-thinking" model.
            "thinking": "off" if no_thinking else meta.get("thinking", "on"),
            "onboardingDefaults": config.get("skipOnboardingDefaults", {}),
            # App-wide launch arguments (app.md) come first, then the scenario's own.
            "launchArgs": config.get("launchArgs", []) + meta.get("launchArgs", []),
            "simulatorId": config.get("simulatorId") or resolve_udid(config["simulatorName"]),
            "projectPath": config["projectPath"],
            "scheme": config["scheme"],
            "configuration": config.get("configuration", "Debug"),
            "bundleId": config["bundleId"],
            "goal": args.goal or parts.get("goal", ""),
            "customGoal": bool(args.goal),
            "doneWhen": "no fixed end" if args.goal else parts.get("done when", "no fixed end"),
            "persona": args.persona or parts.get("persona", ""),
            "appNotes": app_notes,
        }
        self.write_json("run.json", self.meta)
        self.steps, self.findings, self.segments = [], [], []
        self.cost = {}
        self.tokens = {}
        self.live = None
        self.lock = threading.Lock()
        self.state = "preparing"
        self.message = ""
        self.update()

    def write_json(self, name, data, base=None):
        path = (base or self.dir) / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        tmp.replace(path)

    def append_jsonl(self, name, records):
        with (self.dir / name).open("a") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def add_cost(self, result):
        for model, usage in (result.get("modelUsage") or {}).items():
            self.cost[model] = self.cost.get(model, 0) + usage.get("costUSD", 0)
            tokens = self.tokens.setdefault(model, dict.fromkeys(TOKEN_KINDS, 0))
            for kind, key in TOKEN_KINDS.items():
                tokens[kind] += usage.get(key, 0)

    def token_totals(self):
        return {kind: sum(t[kind] for t in self.tokens.values()) for kind in TOKEN_KINDS}

    def update(self, state=None, message=None):
        with self.lock:
            self._update(state, message)

    def _update(self, state, message):
        if state:
            self.state = state
        if message is not None:
            self.message = message
        counts = {s: sum(1 for f in self.findings if f.get("severity") == s) for s in SEVERITY}
        status = {
            "state": self.state,
            "message": self.message,
            "runDir": self.dir.name,
            "app": self.meta["appName"],
            "scenario": self.meta["scenarioName"],
            "goal": self.meta["goal"],
            "model": self.meta["model"] or "haiku",
            "effort": self.meta["effort"] or "low",
            "reportModel": self.meta["reportModel"],
            "narrate": self.meta["narrate"],
            "thinking": self.meta["thinking"],
            "persona": self.meta["persona"],
            "appId": self.meta["app"],
            "scenarioId": self.meta["scenario"],
            "customGoal": self.meta["customGoal"],
            "start": self.meta["start"],
            "updated": now().isoformat(timespec="seconds"),
            "pid": os.getpid(),
            "steps": len(self.steps),
            "maxSteps": self.meta["maxSteps"],
            "segments": len(self.segments),
            "findings": counts,
            "costUSD": round(sum(self.cost.values()), 4),
            "costByModel": {k: round(v, 4) for k, v in self.cost.items()},
            "tokens": self.token_totals(),
            "tokensByModel": self.tokens,
            "segmentSummaries": [s["summary"] for s in self.segments],
            "recentSteps": self.steps[-12:],
            "recentFindings": self.findings[-10:],
            "live": self.live,
        }
        self.write_json("status.json", status)
        self.write_json("latest.json", status, ROOT / "runs")


# ---------- app ----------

def write_mcp_config(run):
    m = run.meta
    path = ROOT / ".mobilebuildmcp" / "config.yaml"
    path.parent.mkdir(exist_ok=True)
    # simulatorId only: with a simulatorName, MobileBuildMCP re-resolves the
    # name and can pick the same model on an older runtime.
    path.write_text(
        "schemaVersion: 1\n"
        "sessionDefaults:\n"
        f"  projectPath: {m['projectPath']}\n"
        f"  scheme: {m['scheme']}\n"
        f"  configuration: {m['configuration']}\n"
        f"  simulatorId: {m['simulatorId']}\n"
        f"  bundleId: {m['bundleId']}\n"
        "  simulatorPlatform: iOS Simulator\n"
    )


def source_fingerprint(project_path):
    """Hash of the app repo's commit, uncommitted changes, and untracked files, or None outside git."""
    repo = Path(project_path).parent
    git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True)
    head = git("rev-parse", "HEAD")
    if head.returncode != 0:
        return None
    digest = hashlib.sha256(head.stdout + git("diff", "HEAD", "--binary").stdout)
    for name in sorted(git("ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0")):
        if name:
            digest.update(name + (repo / name.decode()).read_bytes())
    return digest.hexdigest()


def build_and_launch(run):
    m = run.meta
    udid = m["simulatorId"]
    log = run.dir / "build.log"
    subprocess.run(["xcrun", "simctl", "boot", udid], capture_output=True)
    subprocess.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", udid], capture_output=True)

    key = f"{m['projectPath']}|{m['scheme']}|{m['configuration']}"
    fingerprint = source_fingerprint(m["projectPath"])
    try:
        fingerprints = json.loads(BUILD_FINGERPRINTS.read_text())
    except (OSError, ValueError):
        fingerprints = {}
    products = DERIVED_DATA / "Build" / "Products" / f"{m['configuration']}-iphonesimulator"
    if fingerprint and fingerprints.get(key) == fingerprint and any(products.glob("*.app")):
        log.write_text(f"Skipped: app sources unchanged since the last build ({fingerprint[:12]}).\n")
    else:
        run.update("building", "Building the app")
        with log.open("w") as f:
            build = subprocess.run(
                ["xcodebuild", "-project", m["projectPath"], "-scheme", m["scheme"],
                 "-configuration", m["configuration"], "-destination", f"id={udid}",
                 "-derivedDataPath", str(DERIVED_DATA), "build"],
                stdout=f, stderr=subprocess.STDOUT,
            )
        if build.returncode != 0:
            tail = log.read_text().splitlines()
            errors = [line for line in tail if "error:" in line] or tail[-30:]
            raise BuildFailed("\n".join(errors[-30:]))
        if fingerprint:
            fingerprints[key] = fingerprint
            BUILD_FINGERPRINTS.write_text(json.dumps(fingerprints, indent=2) + "\n")

    app = None
    for candidate in products.glob("*.app"):
        bundle = subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleIdentifier",
                                 str(candidate / "Info.plist")], capture_output=True, text=True).stdout.strip()
        if bundle == m["bundleId"]:
            app = candidate
    if app is None:
        raise BuildFailed(f"No .app with bundle id {m['bundleId']} in {products}")

    run.update("installing", "Installing and launching")
    if m["freshStart"]:
        subprocess.run(["xcrun", "simctl", "uninstall", udid, m["bundleId"]], capture_output=True)
    subprocess.run(["xcrun", "simctl", "install", udid, str(app)], check=True, capture_output=True)
    if m["skipOnboarding"]:
        skip_onboarding(m)
    subprocess.run(["xcrun", "simctl", "launch", "--terminate-running-process", udid, m["bundleId"],
                    *m["launchArgs"]], check=True, capture_output=True)


def skip_onboarding(m):
    """Marks onboarding finished before launch by writing app.md skipOnboardingDefaults into the
    app's own preferences plist, inside its data container, so deleting the app removes them.
    (`simctl spawn defaults write` would write the simulator-wide domain, which outlives the app.)"""
    if not m["onboardingDefaults"]:
        raise SystemExit("skipOnboarding needs skipOnboardingDefaults in app.md")
    udid, bundle = m["simulatorId"], m["bundleId"]
    subprocess.run(["xcrun", "simctl", "terminate", udid, bundle], capture_output=True)
    container = subprocess.run(["xcrun", "simctl", "get_app_container", udid, bundle, "data"],
                               check=True, capture_output=True, text=True).stdout.strip()
    path = Path(container) / "Library" / "Preferences" / f"{bundle}.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    prefs = plistlib.loads(path.read_bytes()) if path.exists() else {}
    path.write_bytes(plistlib.dumps({**prefs, **m["onboardingDefaults"]}))


def relaunch_app(run):
    """Brings the app back to the front with its launch arguments after the bot left it."""
    m = run.meta
    run.update(message="Bringing the app back")
    subprocess.run(["xcrun", "simctl", "launch", "--terminate-running-process", m["simulatorId"],
                    m["bundleId"], *m["launchArgs"]], capture_output=True)


class BuildFailed(Exception):
    pass


# ---------- segments ----------

TOOL_NAMES = {"snapshot_ui": "look", "wait_for_ui": "wait", "tap": "tap", "touch": "tap", "batch": "tap (batch)",
              "long_press": "long press", "swipe": "swipe", "type_text": "type", "button": "button",
              "key_press": "key", "screenshot": "screenshot", "launch_app_sim": "relaunch", "StructuredOutput": "report"}
# Tools that act on the app; each call is one step.
APP_ACTIONS = {"touch", "tap", "type_text", "swipe", "long_press", "button", "key_press"}
TARGET = re.compile(r"(e\d+)\|[^|]*\|([^|]*)\|([^|]*)\|")


class Live:
    """Turns a claude -p stream into live actions in status.json."""

    def __init__(self, run, segment):
        self.run, self.segment = run, segment
        self.labels = {}
        self.usage = {}
        run.live = {"segment": segment, "toolCalls": 0, "steps": 0, "actions": [],
                    "tokens": dict.fromkeys(TOKEN_KINDS, 0)}
        run.update()

    def handle_codex(self, event):
        item = event.get("item") or {}
        if event.get("type") == "thread.started":
            self.codex_thread = event.get("thread_id")
        elif event.get("type") == "item.started" and item.get("type") == "mcp_tool_call":
            # codex exec --json reports usage only when the turn ends; its session log has a
            # running total after every model call.
            usage = self.codex_log_usage()
            if usage:
                self.run.live["tokens"] = codex_usage(usage)
        if event.get("type") == "turn.completed":
            self.run.live["tokens"] = codex_usage(event.get("usage") or {})
        elif item.get("type") == "agent_message" and event.get("type") == "item.completed":
            self.note(item.get("text", ""))
        elif item.get("type") != "mcp_tool_call":
            return
        elif event.get("type") == "item.started":
            self.action({"name": item.get("tool", ""), "input": item.get("arguments") or {}})
        elif event.get("type") == "item.completed":
            for ref, role, label in TARGET.findall(json.dumps(item.get("result"))):
                self.labels[ref] = label or role
            return
        self.run.update()

    def codex_log_usage(self):
        """Latest total_token_usage in this segment's Codex session log (~/.codex/sessions)."""
        thread = getattr(self, "codex_thread", None)
        if not thread:
            return None
        if not getattr(self, "codex_log", None):
            found = sorted((Path.home() / ".codex" / "sessions").glob(f"*/*/*/rollout-*{thread}.jsonl"))
            if not found:
                return None
            self.codex_log = found[-1]
        usage = None
        for line in self.codex_log.read_text().splitlines():
            if '"token_count"' in line:
                try:
                    usage = json.loads(line)["payload"]["info"]["total_token_usage"]
                except (ValueError, KeyError, TypeError):
                    continue
        return usage

    def handle(self, event):
        message = event.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            return
        changed = False
        usage = message.get("usage")
        if event.get("type") == "assistant" and usage and message.get("id"):
            # A message streams as several events with the same id; keep the latest usage.
            self.usage[message["id"]] = usage
            self.run.live["tokens"] = {
                "input": sum(u.get("input_tokens", 0) for u in self.usage.values()),
                "cacheRead": sum(u.get("cache_read_input_tokens", 0) for u in self.usage.values()),
                "cacheWrite": sum(u.get("cache_creation_input_tokens", 0) for u in self.usage.values()),
                "output": sum(u.get("output_tokens", 0) for u in self.usage.values()),
            }
            changed = True
        for block in message["content"]:
            if block.get("type") == "tool_use":
                self.action(block)
                changed = True
            elif block.get("type") == "text" and event.get("type") == "assistant":
                self.note(block.get("text", ""))
                changed = True
            elif block.get("type") == "tool_result":
                text = json.dumps(block.get("content"))
                for ref, role, label in TARGET.findall(text):
                    self.labels[ref] = label or role
        if changed:
            self.run.update()

    def note(self, text):
        """Adds the bot's narration (only written with --narrate) to the live feed."""
        text = text.strip()
        if not text or text.startswith("{"):
            return
        self.run.live["actions"] = (self.run.live["actions"] + [{
            "time": now().strftime("%H:%M:%S"), "tool": "komentar", "detail": text[:200],
        }])[-15:]

    def action(self, block):
        name = block.get("name", "").removeprefix("mcp__mobilebuildmcp__")
        args = block.get("input") or {}
        ref = args.get("elementRef") or args.get("withinElementRef")
        detail = self.labels.get(ref, ref or "")
        if name == "type_text":
            detail = f"{detail}: {args.get('text', '')}"
        elif name == "swipe":
            detail = f"{args.get('direction', '')} {detail}".strip()
        elif name == "wait_for_ui":
            detail = args.get("predicate", "")
        elif name == "button":
            detail = args.get("buttonType", "")
        elif name == "batch":
            detail = ", ".join(self.labels.get(s.get("elementRef"), s.get("elementRef", "")) for s in args.get("steps", []))
        self.run.live["toolCalls"] += 1
        if name in APP_ACTIONS:
            self.run.live["steps"] += 1
        self.run.live["actions"] = (self.run.live["actions"] + [{
            "time": now().strftime("%H:%M:%S"), "tool": TOOL_NAMES.get(name, name), "detail": detail,
        }])[-15:]



def build_prompt(run):
    m = run.meta
    steps_left = m["maxSteps"] - len(run.steps)
    earlier = " ".join(f"{s['segment']}) {s['summary']}" for s in run.segments) or \
        "none, this is the first segment"
    return (f"Goal: {m['goal']}\n"
            f"Done when: {m['doneWhen']}\n"
            f"Persona: {m['persona']}\n"
            f"App notes: {m['appNotes']}\n"
            f"Earlier segments: {earlier}\n"
            f"Steps in this segment: {segment_budget(steps_left)}\n\n{RULES}"
            + (f"\n\n{NARRATE_NOTE}" if m["narrate"] else ""))


def segment_budget(steps_left):
    """Steps for the next segment. A tail shorter than MIN_SEGMENT_STEPS joins
    this segment, since every segment has a fixed startup cost."""
    if steps_left - SEGMENT_STEPS < MIN_SEGMENT_STEPS:
        return steps_left
    return SEGMENT_STEPS


def run_segment(run):
    if is_openai(run.meta["model"]):
        return run_segment_codex(run)
    number = len(run.segments) + 1
    prompt = build_prompt(run)
    (run.dir / f"segment-{number}-prompt.txt").write_text(prompt)
    live = Live(run, number)
    result = None
    with (run.dir / f"segment-{number}.jsonl").open("w") as raw:
        model = ["--model", run.meta["model"]] if run.meta["model"] else []
        if run.meta["effort"]:
            model += ["--effort", run.meta["effort"]]
        proc = subprocess.Popen(
            [claude_bin(), "-p", "--agent", "medstime-probe", *model, "--json-schema", SCHEMA.read_text(),
             "--output-format", "stream-json", "--verbose", prompt],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            # The bot calls the model every few seconds, and each read renews a
            # 5-minute cache, so the pricier 1-hour writes buy nothing.
            env={**os.environ, "CLAUDE_CODE_PROMPT_CACHE_TTL": "5m",
                 **({"MAX_THINKING_TOKENS": "0"} if run.meta["thinking"] == "off" else {})},
        )
        for line in proc.stdout:
            raw.write(line)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "result":
                result = event
            else:
                live.handle(event)
        proc.wait()
    if result is None:
        result = {"is_error": True, "result": (run.dir / f"segment-{number}.jsonl").read_text()[-2000:]}
    run.add_cost(result)
    data = result.get("structured_output")
    if data is None:
        # Haiku sometimes writes the JSON as text instead of calling the tool.
        for text in [str(result.get("result", ""))] + assistant_texts(result.get("session_id")):
            data = json_from_text(text)
            if data is not None:
                break
        result["parsedFromText"] = data is not None
    return data, result


def run_segment_codex(run):
    number = len(run.segments) + 1
    meta, instructions = parse_front_matter(AGENT)
    tools = [t.strip().removeprefix("mcp__mobilebuildmcp__") for t in meta["tools"].split(",")
             if t.strip().startswith("mcp__mobilebuildmcp__")]
    prompt = f"{instructions}\n\n{CODEX_NOTE}\n\n{build_prompt(run)}"
    (run.dir / f"segment-{number}-prompt.txt").write_text(prompt)
    live = Live(run, number)
    model = run.meta["model"]
    texts, usage = [], {}
    with (run.dir / f"segment-{number}.jsonl").open("w") as raw:
        proc = codex_exec(model, run.meta["effort"] or "low", SCHEMA, prompt, codex_mcp_config(tools))
        for line in proc.stdout:
            raw.write(line)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                texts.append(item.get("text", ""))
            if event.get("type") == "turn.completed":
                usage = event.get("usage") or {}
            live.handle_codex(event)
        proc.wait()
    if not texts:
        texts = [(run.dir / f"segment-{number}.jsonl").read_text()[-2000:]]
    result = codex_result(model, usage, texts[-1])
    run.add_cost(result)
    data = None
    for text in texts[::-1]:
        data = json_from_text(text)
        if data is not None:
            break
    return data, result


def assistant_texts(session_id):
    """Assistant text blocks of a claude -p session, newest first."""
    if not session_id:
        return []
    texts = []
    for path in (Path.home() / ".claude" / "projects").glob(f"*/{session_id}.jsonl"):
        for line in path.read_text().splitlines():
            try:
                message = json.loads(line).get("message")
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("role") == "assistant" and isinstance(message.get("content"), list):
                texts += [c["text"] for c in message["content"] if c.get("type") == "text"]
    return texts[::-1]


def json_from_text(text):
    """Return the segment JSON embedded in text if it matches the schema, else None."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if matches(data, json.loads(SCHEMA.read_text())) else None


def matches(value, schema):
    """Check value against the small JSON Schema subset used in segment_schema.json."""
    if "enum" in schema:
        return value in schema["enum"]
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    if kind is not None and not any(
            (k == "object" and isinstance(value, dict)) or (k == "array" and isinstance(value, list))
            or (k == "string" and isinstance(value, str)) or (k == "null" and value is None)
            or (k == "integer" and isinstance(value, int) and not isinstance(value, bool))
            for k in kinds):
        return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            return False
        if schema.get("additionalProperties") is False and any(key not in props for key in value):
            return False
        return all(matches(value[key], props[key]) for key in value if key in props)
    if isinstance(value, list):
        return all(matches(item, schema.get("items", {})) for item in value)
    return True


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "screen").lower()).strip("-")[:40] or "screen"


def record_segment(run, data, result):
    segment = len(run.segments) + 1
    if not data:
        data = {
            "status": "stuck",
            "summary": "The bot did not return a structured result.",
            "steps": [],
            "findings": [{"severity": "bug", "screen": "(run)", "title": "Bot returned no structured result",
                          "details": "```\n" + str(result.get("result", ""))[:2000] + "\n```",
                          "screenshot": None}],
        }

    copied = {}

    def copy_shot(source, number, label):
        if not source:
            return None
        if source not in copied:
            path = Path(source)
            if not path.exists():
                return None
            name = f"{number:03d}-{slug(label)}{path.suffix or '.png'}"
            shutil.copy(path, run.dir / "screenshots" / name)
            copied[source] = f"screenshots/{name}"
        return copied[source]

    new_steps = []
    for step in data["steps"]:
        number = len(run.steps) + len(new_steps) + 1
        record = {"segment": segment, "step": number, **step}
        record["screenshot"] = copy_shot(step.get("screenshot"), number, step.get("screen"))
        new_steps.append(record)

    new_findings = []
    for finding in data["findings"]:
        source = finding.get("screenshot")
        local = finding.get("step")
        if isinstance(local, int) and 1 <= local <= len(new_steps):
            number = new_steps[local - 1]["step"]
        else:
            number = len(run.steps) + len(new_steps)
        record = {**finding, "segment": segment, "step": number}
        record["screenshot"] = copy_shot(source, number, finding.get("title"))
        new_findings.append(record)

    entry = {"segment": segment, "status": data["status"], "summary": data["summary"],
             "steps": len(new_steps), "costUSD": round(result.get("total_cost_usd") or 0, 4),
             "parsedFromText": bool(result.get("parsedFromText"))}
    run.steps += new_steps
    run.findings += new_findings
    run.segments.append(entry)
    run.append_jsonl("steps.jsonl", new_steps)
    run.append_jsonl("findings.jsonl", new_findings)
    run.append_jsonl("segments.jsonl", [entry])
    return data["status"]


# ---------- report ----------

def cell(value):
    return str(value if value is not None else "-").replace("|", "\\|").replace("\n", " ")


def ask_report_model(run):
    data = {
        "run": {k: run.meta[k] for k in ("appName", "scenarioName", "goal", "doneWhen", "persona", "maxSteps")},
        "segments": run.segments,
        "findings": run.findings,
        "steps": [{k: s.get(k) for k in ("step", "screen", "action", "target", "result", "observation")}
                  for s in run.steps],
    }
    model = run.meta["reportModel"]
    prompt = (REPORT_PROMPT.replace("{model}", run.meta["model"] or "claude-haiku-4-5")
              .replace("{data}", json.dumps(data, ensure_ascii=False)))
    if is_openai(model):
        return ask_codex_report(run, model, prompt)
    proc = subprocess.run(
        [claude_bin(), "-p", "--model", model, "--effort", "low", "--tools", "", "--strict-mcp-config",
         "--system-prompt", "You write concise, factual QA reports from run data.",
         "--json-schema", json.dumps(REPORT_SCHEMA),
         "--output-format", "json", prompt],
        cwd=ROOT, capture_output=True, text=True,
    )
    (run.dir / "report-model.json").write_text(proc.stdout or proc.stderr)
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        return None
    run.add_cost(result)
    return result.get("structured_output")


def ask_codex_report(run, model, prompt):
    schema = run.dir / "report-schema.json"
    schema.write_text(json.dumps(REPORT_SCHEMA))
    proc = codex_exec(model, "low", schema, "You write concise, factual QA reports from run data.\n\n" + prompt)
    output = proc.communicate()[0]
    (run.dir / "report-model.jsonl").write_text(output)
    text, usage = "", {}
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if (event.get("item") or {}).get("type") == "agent_message":
            text = event["item"].get("text", "")
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
    run.add_cost(codex_result(model, usage, text))
    try:
        review = json.loads(text)
    except ValueError:
        return None
    return review if matches(review, REPORT_SCHEMA) else None


def fmt_tokens(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def token_rows(run):
    rows = []
    for model, t in [*run.tokens.items(), ("Total", run.token_totals())]:
        rows.append(f"| Tokens, {model} | {fmt_tokens(sum(t.values()))} (input {fmt_tokens(t['input'])}, "
                    f"cache read {fmt_tokens(t['cacheRead'])}, cache write {fmt_tokens(t['cacheWrite'])}, "
                    f"output {fmt_tokens(t['output'])}) |")
    return rows


def write_report(run, outcome, summary, analysis=None):
    seconds = int((now() - run.start).total_seconds())
    offset = run.start.strftime("%z")
    date = f"{run.start.day}. {MONTHS[run.start.month - 1]} {run.start.year}, {run.start:%H:%M:%S} {offset[:3]}:{offset[3:]}"
    results = {r: sum(1 for s in run.steps if s.get("result") == r) for r in ("success", "no_effect", "unexpected")}
    screens = list(dict.fromkeys(s.get("screen") for s in run.steps if s.get("screen")))
    counts = {s: sum(1 for f in run.findings if f.get("severity") == s) for s in SEVERITY}
    shots = sorted((run.dir / "screenshots").glob("*"))
    cost = sum(run.cost.values())
    by_model = ", ".join(f"{k} ${v:.3f}" for k, v in run.cost.items())

    lines = [
        f"# {run.meta['appName']} - {run.meta['scenarioName']}", "",
        f"**Outcome:** {outcome}",
        f"**Date:** {date}",
        f"**Duration:** {seconds // 60:02d}:{seconds % 60:02d}   **Steps:** {len(run.steps)} / "
        f"{run.meta['maxSteps']}   **Segments:** {len(run.segments)}   **Cost:** ${cost:.3f}",
        "", "## Summary", summary, "",
    ]
    if analysis:
        lines += ["## Analysis", analysis, ""]
    lines += [
        "## Stats", "| Metric | Value |", "|---|---|",
        f"| Steps | {len(run.steps)} |",
        f"| Successful / no effect / unexpected | {results['success']} / {results['no_effect']} / {results['unexpected']} |",
        f"| Screens visited | {len(screens)} ({', '.join(screens)}) |",
        f"| Findings | crash {counts['crash']}, bug {counts['bug']}, ux {counts['ux']}, minor {counts['minor']} |",
        f"| Screenshots | {len(shots)} |",
        f"| Cost | ${cost:.3f} ({by_model}) |",
        *token_rows(run),
        "", "## Findings",
    ]
    ordered = sorted(run.findings, key=lambda f: SEVERITY.index(f["severity"]) if f.get("severity") in SEVERITY else 99)
    # Number findings so the path table can link each step to its findings.
    by_step = {}
    for number, f in enumerate(ordered, 1):
        by_step.setdefault(f.get("step"), []).append((number, f))
    if not ordered:
        lines.append("None.")
    for number, f in enumerate(ordered, 1):
        lines += ["", f'<a id="finding-{number}"></a>',
                  f"### {number}. {f.get('severity')}: {f.get('title')}",
                  f"Screen: {f.get('screen')} · Step {f.get('step')}", "", f.get("details", "")]
        if f.get("screenshot"):
            lines += ["", f"![]({f['screenshot']})"]
    lines += ["", "## Path", "| # | Screen | Action | Target | Result |", "|---|---|---|---|---|"]
    for s in run.steps:
        result = cell(s.get("result"))
        links = [f"[{f.get('severity', '').upper()} #{n}](#finding-{n})" for n, f in by_step.get(s["step"], [])]
        if links:
            result += " · " + ", ".join(links)
        lines.append(f"| {s['step']} | {cell(s.get('screen'))} | {cell(s.get('action'))} | "
                     f"{cell(s.get('target'))} | {result} |")
    (run.dir / "report.md").write_text("\n".join(lines) + "\n")


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("app")
    parser.add_argument("scenario")
    parser.add_argument("--steps", type=int, help="override the scenario's maxSteps")
    parser.add_argument("--goal", help="replace the scenario goal; makes the run open-ended")
    parser.add_argument("--persona", help="replace the scenario persona")
    parser.add_argument("--model", help="run the bot on this model instead of the agent's default (haiku)")
    parser.add_argument("--effort", choices=EFFORTS, help="override the agent's effort level (low)")
    parser.add_argument("--report-model", choices=REPORT_MODELS, default=REPORT_MODELS[0],
                        help="model that writes the report summary and analysis, at low effort")
    parser.add_argument("--narrate", action="store_true",
                        help="let the bot announce each action in one sentence (slower; off by default)")
    args = parser.parse_args()

    run = Run(args)
    print(f"Run: {run.dir}", flush=True)
    stopped = {"flag": False}

    def stop(*_):
        stopped["flag"] = True
        run.update(message="Stopping after this segment")
    signal.signal(signal.SIGTERM, stop)

    try:
        write_mcp_config(run)
        build_and_launch(run)
    except BuildFailed as error:
        write_report(run, "build failed", "The build failed:\n\n```\n" + str(error) + "\n```")
        run.update("failed", "Build failed")
        print("Build failed. See", run.dir / "report.md")
        sys.exit(1)

    status = "stuck"
    relaunches = 0
    while len(run.steps) < run.meta["maxSteps"] and not stopped["flag"]:
        run.update("running", f"Segment {len(run.segments) + 1}")
        data, result = run_segment(run)
        status = record_segment(run, data, result)
        if run.live:
            run.live["actions"] = []
            run.live["steps"] = 0
            run.live["tokens"] = dict.fromkeys(TOKEN_KINDS, 0)
        run.update()
        print(f"Segment {len(run.segments)}: {status}, {run.segments[-1]['steps']} steps, "
              f"total {len(run.steps)}/{run.meta['maxSteps']}", flush=True)
        if status in ("goal_reached", "stuck", "crashed"):
            break
        if status == "left_app":
            # The bot has no launch tool, so relaunches always carry the app's launch arguments.
            relaunches = relaunches + 1 if run.segments[-1]["steps"] == 0 else 1
            if relaunches > 2:
                status = "stuck"
                break
            relaunch_app(run)
            continue
        if run.segments[-1]["steps"] == 0:
            status = "stuck"
            break

    outcome = {"goal_reached": "goal reached", "stuck": "stuck", "crashed": "crashed"}.get(status, "budget used")
    if stopped["flag"] and status not in ("goal_reached", "stuck", "crashed"):
        outcome = "stopped"
    run.update("reporting", "Writing the report")
    review = ask_report_model(run)
    if review:
        write_report(run, outcome, review["summary"], review["analysis"])
    else:
        write_report(run, outcome, " ".join(s["summary"] for s in run.segments) or "No summary.")
    run.update("done", outcome)
    print(f"{outcome} · {len(run.steps)}/{run.meta['maxSteps']} steps · ${sum(run.cost.values()):.3f}")
    print(run.dir / "report.md")


if __name__ == "__main__":
    main()
