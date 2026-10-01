---
name: explore-app
description: Run the app-explorer bot on an iOS app in the Simulator. Builds and launches the app, lets the Haiku bot use it in short segments toward a scenario goal, then writes a report with screenshots, findings, and stats under runs/. Use when the user runs /explore-app <app> <scenario>.
argument-hint: <app> <scenario>
---

# Explore an app

Arguments: `<app> <scenario>`, for example `medstime onboarding`.

- App config: `apps/<app>/app.md`
- Scenario: `apps/<app>/scenarios/<scenario>.md`

If either file is missing, list what exists under `apps/` and stop.

## 1. Prepare the run

1. Read the app config and the scenario.
2. Create the run folder `runs/<YYYY-MM-DD-HHMMSS>-<app>-<scenario>/` with a
   `screenshots/` subfolder. Note the start time.
3. Resolve the simulator UDID. Use the config's `simulatorId` if it has one.
   Otherwise run `xcrun simctl list devices available` and take the device
   named `simulatorName` on the newest iOS runtime that has it; the same name
   often exists on several runtimes.
4. Call `mcp__mobilebuildmcp__session_set_defaults` with the config's
   `projectPath`, `scheme`, `configuration`, and `bundleId`, plus
   `simulatorId` set to that UDID.
5. If the scenario has `freshStart: true`, boot the simulator with
   `mcp__mobilebuildmcp__boot_sim` and uninstall the app so it starts with no
   data and no granted permissions: `xcrun simctl uninstall <UDID> <bundleId>`.
   A missing app is fine. Never erase the simulator.
6. Call `mcp__mobilebuildmcp__build_run_sim`, adding the scenario's
   `launchArgs` if it has any. If the build fails, write the build error to
   `report.md` with outcome `build_failed` and stop.

Use only one simulator, the one named in the config.

## 2. Run the bot in segments

Segments keep the bot's context small, so every step stays as fast as the
first. Use 10 steps per segment.

Repeat until a stop condition below:

1. Launch the `app-explorer` agent (foreground) with this prompt:

   ```
   Goal: <scenario goal>
   Done when: <scenario "Done when", or "no fixed end">
   Persona: <scenario persona>
   App notes: <the app config body>
   Earlier segments: <summaries of earlier segments, oldest first, or "none, this is the first segment">
   Steps in this segment: <min(10, steps left)>

   Take a screenshot on each new screen and on the last screen. Your final
   message (or hand-back message) must be only the JSON from your "Reply"
   section, starting with { and ending with }, with screenshot paths filled in.
   ```

   The reply rule is repeated here because agent definitions load when the
   session starts, so edits to the bot only reach it in a new session.

2. Parse the JSON reply. If it is not valid JSON, record the raw reply as a
   `bug` finding against the run itself and treat the segment as `stuck`.
3. Copy each screenshot path in `steps` and `findings` into the run's
   `screenshots/` folder, named `<step number, 3 digits>-<short-slug>.png`,
   and point the record at the copy.
4. Append each step as one JSON line to `steps.jsonl`, adding `segment` and a
   running `step` number. Append each finding to `findings.jsonl` the same way.
5. Keep the segment summary for the next prompt.

Stop when:
- status is `goal_reached`, `stuck`, or `crashed`, or
- the scenario's `maxSteps` is used up.

## 3. Write the report

Write `report.md` in the run folder:

```markdown
# <app> - <scenario name>

**Outcome:** goal reached | budget used | stuck | crashed | build failed
**Date:** <start, e.g. 2. okt 2026, 14:05:12 +02:00>
**Duration:** <mm:ss>   **Steps:** <n> / <maxSteps>   **Segments:** <n>

## Summary
<3-5 sentences: what the bot did, where it ended, the most important problems>

## Stats
| Metric | Value |
|---|---|
| Steps | n |
| Successful / no effect / unexpected | a / b / c |
| Screens visited | n (list) |
| Findings | crash a, bug b, ux c, minor d |
| Screenshots | n |

## Findings
### <severity>: <title>
Screen: <screen> · Step <n>
<details>
![](screenshots/<file>.png)

## Path
| # | Screen | Action | Target | Result |
|---|---|---|---|---|
```

List findings most severe first. Embed only screenshots that exist.

Finish by telling the user, in Serbian, the outcome, the stats line, the top
findings, and the path to `report.md`.
