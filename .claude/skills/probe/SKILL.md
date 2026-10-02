---
name: probe
description: Run the medstime-probe bot on an iOS app in the Simulator through scripts/explore.py, then report the outcome. Use when the user runs /probe <app> <scenario> [steps] [goal].
argument-hint: <app> <scenario> [steps] [goal]
---

# Probe an app

Arguments: `<app> <scenario>`, optionally a step count and a goal, for example
`medstime onboarding` or `medstime autonomous 40 "Try to add and edit a medication"`.

`scripts/explore.py` does the whole run: build, bot segments, report. Do not
drive the Simulator or the bot yourself.

1. Run it in the background (it takes minutes):
   `python3 scripts/explore.py <app> <scenario> [--steps <n>] [--goal "<goal>"]`.
   If it exits at once with a missing app or scenario, list what exists under
   `apps/` and stop.
2. Tell the user the run started and that they can follow it live in the web UI
   (`python3 scripts/server.py`, then http://127.0.0.1:8765).
3. When it finishes, read the `report.md` path it printed and tell the user, in
   Serbian: the outcome line, the top findings, what the analysis flags as
   likely bot errors, and the report path.
