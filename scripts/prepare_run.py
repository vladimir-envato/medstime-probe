#!/usr/bin/env python3
"""Prepare an /explore-app run.

Usage: prepare_run.py <app> <scenario>

Reads apps/<app>/app.md and apps/<app>/scenarios/<scenario>.md, creates the
run folder, resolves the simulator UDID, and for freshStart scenarios boots the
simulator and uninstalls the app. Writes run.json into the run folder and
prints it.
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_front_matter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        return {}, text
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
    found = {}
    for match in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", body, re.S | re.M):
        found[match.group(1).strip().lower()] = match.group(2).strip()
    return found


def resolve_udid(name):
    out = subprocess.run(
        ["xcrun", "simctl", "list", "devices", "available", "-j"],
        check=True, capture_output=True, text=True,
    ).stdout
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
        sys.exit(f"No available simulator named {name!r}")
    return best[1]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    app, scenario = sys.argv[1], sys.argv[2]
    app_path = ROOT / "apps" / app / "app.md"
    scenario_path = ROOT / "apps" / app / "scenarios" / f"{scenario}.md"
    if not app_path.exists() or not scenario_path.exists():
        available = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "apps").rglob("*.md"))
        sys.exit("Missing app or scenario. Available:\n" + "\n".join(available))

    config, app_notes = parse_front_matter(app_path)
    meta, body = parse_front_matter(scenario_path)
    parts = sections(body)

    start = datetime.now().astimezone()
    run_dir = ROOT / "runs" / f"{start:%Y-%m-%d-%H%M%S}-{app}-{scenario}"
    (run_dir / "screenshots").mkdir(parents=True)

    udid = config.get("simulatorId") or resolve_udid(config["simulatorName"])
    if meta.get("freshStart"):
        subprocess.run(["xcrun", "simctl", "boot", udid], capture_output=True)
        subprocess.run(["xcrun", "simctl", "uninstall", udid, config["bundleId"]], capture_output=True)

    run = {
        "app": app,
        "scenario": scenario,
        "appName": config.get("name", app),
        "scenarioName": meta.get("name", scenario),
        "runDir": str(run_dir),
        "start": start.isoformat(timespec="seconds"),
        "maxSteps": int(meta.get("maxSteps", 50)),
        "freshStart": bool(meta.get("freshStart")),
        "launchArgs": meta.get("launchArgs", []),
        "simulatorId": udid,
        "projectPath": config["projectPath"],
        "scheme": config["scheme"],
        "configuration": config.get("configuration", "Debug"),
        "bundleId": config["bundleId"],
        "goal": parts.get("goal", ""),
        "doneWhen": parts.get("done when", "no fixed end"),
        "persona": parts.get("persona", ""),
        "appNotes": app_notes,
    }
    (run_dir / "run.json").write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(run, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
