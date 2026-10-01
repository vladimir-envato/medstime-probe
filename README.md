# app-explorer

An AI bot that uses an iOS app in the Simulator like a real user: it taps,
types, and swipes through the app, judges whether each step worked, flags what
looks broken or confusing, and writes a report with screenshots and stats.

A small, UI-less take on tools like Harness, driven from Claude Code. It runs
on your Claude subscription; no API key is needed.

## Requirements

- macOS with Xcode and an iOS Simulator runtime
- Node.js 18 or later (for `npx`)
- Claude Code

The app under test stays in its own repo. app-explorer only reads its Xcode
project to build it.

## Usage

Open Claude Code in this folder and run:

```
/explore-app medstime onboarding
/explore-app medstime autonomous
```

The first time, Claude Code asks you to approve the `mobilebuildmcp` server
from `.mcp.json`.

Each run writes to `runs/<date>-<app>-<scenario>/`:

| File | Contents |
|---|---|
| `report.md` | Outcome, summary, stats, findings with screenshots, and the path the bot took |
| `steps.jsonl` | One line per action: screen, action, target, intent, result, screenshot |
| `findings.jsonl` | One line per problem: severity, screen, title, details, screenshot |
| `screenshots/` | Screens after meaningful successes and at every suspicious moment |

`runs/` is not committed.

## How it works

```
/explore-app ──► explore-app skill (orchestrator, main session)
                   │  build, install, launch through MobileBuildMCP
                   │  runs the bot in segments of 10 steps
                   ▼
                 app-explorer agent (Haiku 4.5, effort low)
                   │  snapshot_ui → act → snapshot_ui → judge → screenshot
                   ▼
                 MobileBuildMCP ──► xcodebuild / simctl / AXe ──► Simulator
```

- **Orchestrator** (`.claude/skills/explore-app/SKILL.md`): prepares the app,
  starts each segment with a summary of the earlier ones, copies screenshots,
  and writes the report.
- **Bot** (`.claude/agents/app-explorer.md`): the "user". It can only see and
  touch the Simulator; it has no shell or file access. It replies with a JSON
  segment log.
- **Segments**: a fresh bot context every 10 steps keeps each step as fast as
  the first and stops long runs from filling the context.
- **MobileBuildMCP**: the hands and eyes. See below.

### Bot effort

The bot runs at `effort: low` for speed. If it gets stuck on complex screens,
change `effort` in `.claude/agents/app-explorer.md` to `medium`.

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
XcodeBuildMCP, by Sentry, MIT license) is a local MCP server that builds the
app and drives the Simulator. It bundles [AXe](https://github.com/cameroncooke/AXe),
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

Screens and screenshots the bot sees go to Claude as part of the conversation,
like anything else in Claude Code. Use test data in the app.

### Which Xcode

Builds use the Xcode selected by `xcode-select -p`. No Xcode agent integration
is involved, so the Xcode 26.3 requirement on the MobileBuildMCP site does not
apply here.

### Xcode MCP

Xcode 26.3 and later ship Apple's own MCP server (`xcrun mcpbridge`), with tools
for building, running tests, rendering SwiftUI previews, documentation search,
and the Issue Navigator. It has no tools to tap, swipe, or read the Simulator
screen, so it cannot drive the bot. MobileBuildMCP covers everything this
project needs, so Xcode MCP is not used.

Xcode MCP could replace MobileBuildMCP for the build step, and preview
snapshots could check screens without launching the app. MobileBuildMCP can
also proxy Xcode MCP through its `xcode-ide` workflow, which is disabled here.
