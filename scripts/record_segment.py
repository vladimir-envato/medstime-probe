#!/usr/bin/env python3
"""Record one app-explorer segment and print the prompt for the next one.

Usage:
  record_segment.py <run_dir> --agent-id <id>     read the bot's reply from its transcript
  record_segment.py <run_dir> --reply-file <path> read the reply from a file
  record_segment.py <run_dir> --first             only print the first prompt

Parses the bot's JSON reply, copies screenshots into the run, appends to
steps.jsonl, findings.jsonl, and segments.jsonl, and prints a short status
plus the next segment's prompt (or STOP).
"""
import argparse
import json
import re
import shutil
from pathlib import Path

SEGMENT_STEPS = 20
PROJECTS = Path.home() / ".claude" / "projects"

RULES = """Before each tap, call wait_for_ui with predicate "settled" if the screen may still be moving (after launch, a swipe, a page change, a sheet, or an alert); taps during animations are lost. Give every tap and swipe a postDelay of 1. Before marking a step no_effect, wait for settled and retry once; only report a control as broken if the retry also fails. Stay within this segment's step budget.

Work silently: no text between tool calls, no summary at the end. Your final message (or hand-back message) must be only the JSON from your "Reply" section, starting with { and ending with }, with nothing before or after it."""


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_jsonl(path, records):
    with path.open("a") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def reply_from_transcript(agent_id):
    matches = sorted(PROJECTS.glob(f"*/*/subagents/agent-{agent_id}.jsonl"), key=lambda p: p.stat().st_mtime)
    if not matches:
        raise SystemExit(f"No transcript found for agent {agent_id}")
    reply = None
    for line in matches[-1].read_text().splitlines():
        try:
            message = json.loads(line).get("message")
        except ValueError:
            continue
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        for block in message.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "SubagentHandback":
                reply = block["input"].get("message", "")
            elif block.get("type") == "text" and block.get("text", "").strip():
                reply = block["text"]
    return reply or ""


def parse_reply(raw):
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and "status" in data else None


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "screen").lower()).strip("-")[:40] or "screen"


def build_prompt(run, segments, steps_left):
    if segments:
        earlier = " ".join(f"{s['segment']}) {s['summary']}" for s in segments)
    else:
        earlier = "none, this is the first segment"
    return (
        f"Goal: {run['goal']}\n"
        f"Done when: {run['doneWhen']}\n"
        f"Persona: {run['persona']}\n"
        f"App notes: {run['appNotes']}\n"
        f"Earlier segments: {earlier}\n"
        f"Steps in this segment: {min(SEGMENT_STEPS, steps_left)}\n\n"
        f"{RULES}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--agent-id")
    source.add_argument("--reply-file")
    source.add_argument("--first", action="store_true")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run = json.loads((run_dir / "run.json").read_text())
    steps = read_jsonl(run_dir / "steps.jsonl")
    segments = read_jsonl(run_dir / "segments.jsonl")

    if args.first:
        print("NEXT PROMPT:\n" + build_prompt(run, segments, run["maxSteps"]))
        return

    raw = reply_from_transcript(args.agent_id) if args.agent_id else Path(args.reply_file).read_text()
    data = parse_reply(raw)
    segment = len(segments) + 1
    step_no = len(steps)

    if data is None:
        status = "stuck"
        summary = "The bot's reply was not valid JSON."
        new_steps = []
        new_findings = [{
            "severity": "bug", "screen": "(run)",
            "title": "Bot reply was not valid JSON",
            "details": "```\n" + raw[:2000] + "\n```", "screenshot": None,
        }]
    else:
        status = data.get("status", "stuck")
        summary = data.get("summary", "")
        new_steps = data.get("steps", [])
        new_findings = data.get("findings", [])

    copied = {}

    def copy_shot(source, number, label):
        if not source:
            return None
        if source in copied:
            return copied[source]
        path = Path(source)
        if not path.exists():
            return None
        name = f"{number:03d}-{slug(label)}{path.suffix or '.png'}"
        shutil.copy(path, run_dir / "screenshots" / name)
        copied[source] = f"screenshots/{name}"
        return copied[source]

    step_records = []
    for step in new_steps:
        step_no += 1
        record = {"segment": segment, "step": step_no, **step}
        record["screenshot"] = copy_shot(step.get("screenshot"), step_no, step.get("screen"))
        step_records.append(record)

    finding_records = []
    for finding in new_findings:
        source = finding.get("screenshot")
        number = next((r["step"] for r, s in zip(step_records, new_steps) if s.get("screenshot") == source and source), step_no)
        record = {"segment": segment, "step": number, **finding}
        record["screenshot"] = copy_shot(source, number, finding.get("title"))
        finding_records.append(record)

    append_jsonl(run_dir / "steps.jsonl", step_records)
    append_jsonl(run_dir / "findings.jsonl", finding_records)
    append_jsonl(run_dir / "segments.jsonl", [{
        "segment": segment, "status": status, "summary": summary, "steps": len(step_records),
    }])
    segments.append({"segment": segment, "summary": summary})

    steps_left = run["maxSteps"] - step_no
    print(f"Segment {segment}: {status}, {len(step_records)} steps, {len(finding_records)} findings, "
          f"{len(copied)} screenshots. Total {step_no}/{run['maxSteps']}.")
    print(f"Summary: {summary}")
    if status in ("goal_reached", "stuck", "crashed") or steps_left <= 0:
        print("STOP")
    else:
        print("NEXT PROMPT:\n" + build_prompt(run, segments, steps_left))


if __name__ == "__main__":
    main()
