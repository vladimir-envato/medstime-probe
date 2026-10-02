# medstime-probe

An AI bot that uses an iOS app in the Simulator like a real user: it taps,
types, and swipes through the app, judges whether each step worked, flags what
looks broken or confusing, and writes a report with screenshots and stats.

A small take on tools like Harness. The bot runs on Claude (through Claude Code)
or on ChatGPT models (through the Codex CLI), on your existing subscriptions; no
API key is needed.

## Requirements

- macOS with Xcode and an iOS Simulator runtime
- Python 3.9 or later (the one that ships with Xcode is enough)
- Node.js 18 or later (for `npx`, which runs MobileBuildMCP)
- The Claude Code CLI, signed in: `curl -fsSL https://claude.ai/install.sh | bash`,
  then run `claude` once and `/login`
- Optional, for GPT models: the Codex CLI, signed in with a ChatGPT account.
  `explore.py` uses `codex` from `PATH`, or the copy bundled with the ChatGPT
  desktop app (`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`).

The app under test stays in its own repo. medstime-probe only reads its Xcode
project to build it.

## Usage

### Web UI

```
python3 scripts/server.py
```

Open http://127.0.0.1:8765. Pick an app and a scenario, set the number of
steps, the bot's model and effort (low or medium), who writes the report,
optionally write your own goal, and press Start. While the run goes, the
page shows progress, cost, tokens, the bot's latest actions, steps, and
findings; watch the Simulator itself (or Device Hub) to see the screen. Steps
and tokens count up live; cost arrives when a segment ends, so cost and tokens
show grey until then. A step with a finding links to its description and
screenshot. When the run ends, the report appears below; the last 5 runs
are listed on the left, with a count of the rest in `runs/`.

**Istorija nalaza** (`/history`) lists every finding from every run, filterable
by severity, app, scenario, and text, with the bot's own failures hidden by
default. Selecting one shows its details, screenshot, the steps that led to it,
and a link to its run's report. The server listens on localhost only.

### Terminal

```
python3 scripts/explore.py medstime onboarding
python3 scripts/explore.py medstime autonomous --steps 40
python3 scripts/explore.py medstime autonomous --steps 40 --goal "Add a medication, then edit it"
python3 scripts/explore.py medstime autonomous --model gpt-6-sol --report-model gpt-6-sol
```

`--steps` overrides the scenario's step budget. `--goal` replaces the
scenario's goal and makes the run open-ended: the bot explores until the steps
run out. `--persona` replaces the scenario's persona. `--model` runs the bot on
another model (Haiku 4.5 by default; any `gpt-*` model goes through Codex), and
`--effort` sets `low` or `medium`. `--report-model` picks who writes the report:
`claude-sonnet-5-5` (default), `claude-opus-5-5`, or `gpt-6-sol`, always at low
effort.

### Claude Code

In a Claude Code session in this folder, `/probe medstime onboarding`
runs `explore.py` and summarizes the report in chat.

## Output

Each run writes to `runs/<date>-<app>-<scenario>/`:

| File | Contents |
|---|---|
| `report.md` | Outcome, cost and tokens, summary, analysis, stats, findings with screenshots, and the path the bot took (steps with a finding link to it) |
| `steps.jsonl` | One line per action: screen, action, target, intent, result, screenshot |
| `findings.jsonl` | One line per problem: severity, screen, title, details, step, screenshot |
| `segments.jsonl` | One line per segment: status, summary, steps, cost |
| `status.json` | Live progress for the web UI (also copied to `runs/latest.json`) |
| `run.json` | The resolved app config and scenario |
| `screenshots/` | One per finding, taken while the problem was on screen |
| `segment-<n>.jsonl`, `report-model.json(l)` | Raw Claude Code or Codex output, for debugging |

`runs/` is not committed.

## How it works

```
scripts/explore.py  (plain Python, no model)
  │  xcodebuild ──► simctl install / launch
  │
  ├─► segment 1..n:  claude -p --agent medstime-probe --json-schema
  │                    (or codex exec --output-schema for gpt-* models)
  │                    medstime-probe bot (Haiku 4.5, effort low, by default)
  │                      look ─► touch / type / swipe ─► judge ─► screenshot
  │                      MobileBuildMCP ──► AXe ──► Simulator
  │                    returns a JSON segment log
  │
  └─► report:        Sonnet 5.5, Opus 5.5, or GPT-6 Sol, effort low
                       summary + analysis of the whole run
```

The rule of thumb: what is deterministic is in the script; only judgment goes
to a model.

- **`scripts/explore.py`** runs everything that needs no judgment: the build,
  a fresh install, each segment, recording steps and screenshots, stop
  conditions, the report tables, and the live status. No model orchestrates.
- **Bot** (`.claude/agents/medstime-probe.md`): the "user", on Haiku by
  default. It can only see and touch the Simulator; it has no shell or file
  access. On a GPT model, `codex exec` gets the same instructions, the same
  MobileBuildMCP tools (from `.mcp.json`), and a read-only sandbox.
- **Segments**: every segment is a fresh `claude -p` session that gets the goal
  and a short summary of the earlier segments, so step 40 is as fast and cheap
  as step 1. Segments have 10 steps; a tail under 3 steps joins the previous
  segment (`SEGMENT_STEPS` and `MIN_SEGMENT_STEPS` in `explore.py`). Longer
  segments did not cost less: they read less cache but wrote more output.
- **Structured result**: the bot returns its segment log through the
  `StructuredOutput` tool, which Claude Code checks against
  `scripts/segment_schema.json`. If Haiku writes the JSON as text instead,
  `explore.py` recovers it from the session and validates it against the same
  schema; otherwise the segment is recorded as `stuck`.
- **Report**: one call to the report model at the end writes the summary and an analysis:
  which findings matter, which look like the bot's own mistakes, and what to
  check by hand.
- **Waiting**: the bot acts on the screen each tap or swipe returns and calls
  `wait_for_ui` only when that screen still looks mid-animation. Waiting
  after every action doubled the model turns per step and, in measured runs,
  always returned the same screen.
- **Taps**: the bot taps with a 0.15 s touch, and focuses a text field and
  checks for the keyboard before typing. Short taps were often ignored, and
  typing into an unfocused field is silently lost.
- **Screenshots** only when something looks wrong: every finding must carry
  one (the schema rejects a finding without it), and nothing else gets one.
- **Paywalls**: the bot buys a plan; the purchase sheet is the local StoreKit
  test environment, so nothing is charged. It never signs in to an Apple
  Account and reports a finding if asked to.
- **Permissions**: the bot always allows notifications and skips alarms.
- **Settings is off limits**: the bot never opens the iOS Settings app or
  presses Home. If another app comes to the front anyway, it taps "◀ <app>"
  in the status bar, or relaunches the app with `launch_app_sim` when the
  snapshot does not list that link.

### Cost

On a Claude subscription the runs count against your usage; the report shows
the equivalent API list price, plus token counts by model and kind. Measured
so far: onboarding about $0.09-0.11, a 20-step autonomous run about $0.22. The
bot is most of it, and output tokens weigh far more than cache reads.

GPT runs go through your ChatGPT plan; Codex reports no dollar cost, so they
show $0 with token counts.

### Bot effort

The bot runs at `effort: low` for speed. If it gets stuck on complex screens,
pick `medium` in the web UI or pass `--effort medium`. Higher levels are not
offered; they cost more without helping the bot.

## Adding an app or scenario

```
apps/<app>/app.md                 project path, scheme, bundle id, simulator, notes for the bot
apps/<app>/scenarios/<name>.md    goal, persona, step budget, fresh start
```

Scenario front matter:

| Key | Meaning |
|---|---|
| `name` | Title in the report |
| `freshStart` | `true` uninstalls the app first: no data, no permissions |
| `maxSteps` | Step budget for the whole run |
| `launchArgs` | Optional launch arguments, for example `["-reset-onboarding"]` |

The body has `## Goal`, `## Persona`, and an optional `## Done when`. Leave out
`Done when` for open-ended exploration.

## MobileBuildMCP

[MobileBuildMCP](https://github.com/getsentry/MobileBuildMCP) (formerly
XcodeBuildMCP, by Sentry, MIT license) is a local MCP server that drives the
Simulator for the bot. It bundles [AXe](https://github.com/cameroncooke/AXe),
which performs taps and reads the screen through accessibility, so there is no
WebDriverAgent to build.

`.mcp.json` pins and restricts it:

- **Pinned version** (`mobilebuildmcp@2.7.1`): `npx` downloads it once into the
  npm cache and reuses it; it never updates on its own. Bump the version on
  purpose after reviewing the release.
- **Sentry telemetry off** (`MOBILEBUILDMCP_SENTRY_DISABLED=true`): nothing is
  sent to Sentry.
- **Only two workflows** (`simulator`, `ui-automation`): no debugger, device,
  or Xcode IDE tools.

`explore.py` writes the simulator to `.mobilebuildmcp/config.yaml` (not
committed) before each run. It writes only the UDID: with a simulator name,
MobileBuildMCP re-resolves the name and can pick the same model on an older
runtime.

Screens and screenshots the bot sees go to Claude as part of the conversation,
like anything else in Claude Code. Use test data in the app.

### Which Xcode

`explore.py` builds with `xcodebuild`, using the Xcode selected by
`xcode-select -p`, into `.build/DerivedData` (not committed). No Xcode agent
integration is involved, so the Xcode 26.3 requirement on the MobileBuildMCP
site does not apply here.

### Xcode MCP

Xcode 26.3 and later ship Apple's own MCP server (`xcrun mcpbridge`), with tools
for building, running tests, rendering SwiftUI previews, documentation search,
and the Issue Navigator. It has no tools to tap, swipe, or read the Simulator
screen, so it cannot drive the bot. MobileBuildMCP covers everything this
project needs, so Xcode MCP is not used.

Xcode MCP could replace MobileBuildMCP for the build step, and preview
snapshots could check screens without launching the app. MobileBuildMCP can
also proxy Xcode MCP through its `xcode-ide` workflow, which is disabled here.
