---
name: explore-app
description: Run the app-explorer bot on an iOS app in the Simulator. Builds and launches the app, lets the Haiku bot use it in short segments toward a scenario goal, then writes a report with screenshots, findings, and stats under runs/. Use when the user runs /explore-app <app> <scenario>.
argument-hint: <app> <scenario>
---

# Explore an app

Arguments: `<app> <scenario>`, for example `medstime onboarding`.

The scripts in `scripts/` do the bookkeeping. Keep your own calls to the ones
below; do not read run files or screenshots yourself unless a script fails.

## 1. Prepare

1. Run `python3 scripts/prepare_run.py <app> <scenario>`. It creates the run
   folder, resolves the simulator, and for `freshStart` scenarios boots it and
   uninstalls the app. If it fails, show its output and stop. Its JSON output
   is the run: keep `runDir`.
2. Call `mcp__mobilebuildmcp__session_set_defaults` with `projectPath`,
   `scheme`, `configuration`, `bundleId`, and `simulatorId` from that output.
3. Call `mcp__mobilebuildmcp__build_run_sim`, passing `launchArgs` if the run
   has any. If the build fails, save the error to `<runDir>/build-error.txt`,
   run `python3 scripts/finish_run.py <runDir> --build-failed <runDir>/build-error.txt`,
   tell the user, and stop.
4. Run `python3 scripts/record_segment.py <runDir> --first` to get the first
   prompt.

Use only the simulator the run names. Never erase it.

## 2. Run the bot in segments

Repeat:

1. Launch the `app-explorer` agent (foreground) with the prompt after
   `NEXT PROMPT:`, exactly as printed.
2. Run `python3 scripts/record_segment.py <runDir> --agent-id <agentId>` with
   the agent id from the launch result. It reads the bot's reply from its
   transcript, records steps, findings, and screenshots, and prints either
   `STOP` or the next prompt. If it cannot find the transcript, write the
   bot's reply to `<runDir>/reply.json` and use `--reply-file` instead.
3. On `STOP`, go to step 3. Otherwise repeat with the new prompt.

## 3. Report

Run `python3 scripts/finish_run.py <runDir> --summary "<3-5 sentences>"`. The
summary says what the bot did, where it ended, and the most important
problems; base it on the segment summaries the script printed.

Finish by telling the user, in Serbian, the outcome line the script printed,
the top findings, and the path to `report.md`.
