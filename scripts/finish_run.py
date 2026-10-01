#!/usr/bin/env python3
"""Write report.md for an /explore-app run.

Usage:
  finish_run.py <run_dir> --summary "<3-5 sentences>"
  finish_run.py <run_dir> --build-failed <file with the build error>

Builds the header, stats, findings, and path from run.json, steps.jsonl,
findings.jsonl, and segments.jsonl. Only the summary comes from the caller.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "avg", "sep", "okt", "nov", "dec"]
SEVERITY = ["crash", "bug", "ux", "minor"]
OUTCOMES = {"goal_reached": "goal reached", "stuck": "stuck", "crashed": "crashed"}


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cell(value):
    return str(value if value is not None else "-").replace("|", "\\|").replace("\n", " ")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--summary")
    group.add_argument("--build-failed")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run = json.loads((run_dir / "run.json").read_text())
    steps = read_jsonl(run_dir / "steps.jsonl")
    findings = read_jsonl(run_dir / "findings.jsonl")
    segments = read_jsonl(run_dir / "segments.jsonl")

    start = datetime.fromisoformat(run["start"])
    seconds = int((datetime.now().astimezone() - start).total_seconds())
    offset = start.strftime("%z")
    date = f"{start.day}. {MONTHS[start.month - 1]} {start.year}, {start:%H:%M:%S} {offset[:3]}:{offset[3:]}"

    if args.build_failed:
        outcome = "build failed"
        summary = "The build failed:\n\n```\n" + Path(args.build_failed).read_text()[-4000:] + "\n```"
    else:
        last = segments[-1]["status"] if segments else "stuck"
        outcome = OUTCOMES.get(last, "budget used")
        summary = args.summary

    results = {r: sum(1 for s in steps if s.get("result") == r) for r in ("success", "no_effect", "unexpected")}
    screens = list(dict.fromkeys(s.get("screen") for s in steps if s.get("screen")))
    counts = {sev: sum(1 for f in findings if f.get("severity") == sev) for sev in SEVERITY}
    shots = sorted((run_dir / "screenshots").glob("*"))

    lines = [
        f"# {run['appName']} - {run['scenarioName']}",
        "",
        f"**Outcome:** {outcome}",
        f"**Date:** {date}",
        f"**Duration:** {seconds // 60:02d}:{seconds % 60:02d}   **Steps:** {len(steps)} / {run['maxSteps']}   "
        f"**Segments:** {len(segments)}",
        "",
        "## Summary",
        summary,
        "",
        "## Stats",
        "| Metric | Value |",
        "|---|---|",
        f"| Steps | {len(steps)} |",
        f"| Successful / no effect / unexpected | {results['success']} / {results['no_effect']} / {results['unexpected']} |",
        f"| Screens visited | {len(screens)} ({', '.join(screens)}) |",
        f"| Findings | crash {counts['crash']}, bug {counts['bug']}, ux {counts['ux']}, minor {counts['minor']} |",
        f"| Screenshots | {len(shots)} |",
        "",
        "## Findings",
    ]
    ordered = sorted(findings, key=lambda f: SEVERITY.index(f["severity"]) if f.get("severity") in SEVERITY else 99)
    if not ordered:
        lines.append("None.")
    for f in ordered:
        lines += ["", f"### {f.get('severity')}: {f.get('title')}",
                  f"Screen: {f.get('screen')} · Step {f.get('step')}", "", f.get("details", "")]
        if f.get("screenshot") and (run_dir / f["screenshot"]).exists():
            lines += ["", f"![]({f['screenshot']})"]

    lines += ["", "## Path", "| # | Screen | Action | Target | Result |", "|---|---|---|---|---|"]
    for s in steps:
        lines.append(f"| {s['step']} | {cell(s.get('screen'))} | {cell(s.get('action'))} | "
                     f"{cell(s.get('target'))} | {cell(s.get('result'))} |")
    if shots:
        lines += ["", f"![]({shots[-1].relative_to(run_dir)})"]

    (run_dir / "report.md").write_text("\n".join(lines) + "\n")
    print(f"{outcome} · {len(steps)}/{run['maxSteps']} steps · {len(segments)} segments · "
          f"{seconds // 60:02d}:{seconds % 60:02d} · findings crash {counts['crash']}, bug {counts['bug']}, "
          f"ux {counts['ux']}, minor {counts['minor']}")
    print(run_dir / "report.md")


if __name__ == "__main__":
    main()
