# medstime-probe

An AI bot that uses an iOS app in the Simulator like a real user: it taps,
types, and swipes through the app, judges whether each step worked, flags what
looks broken or confusing, and writes a report with screenshots and stats.

A small take on tools like Harness. The bot runs on Claude (through Claude Code)
or on ChatGPT models (through the Codex CLI), on your existing subscriptions; no
API key is needed.

## Terms

| Term | Meaning | Example |
|---|---|---|
| **Scenario** | The task for a whole run: goal, persona, step budget, and presets (fresh start, skip onboarding, thinking). One file in `apps/<app>/scenarios/`. | Add Medication flow: open Add Medication and try to break the form, 50 steps, onboarding skipped |
| **Persona** | The user the bot plays; it shapes which actions the bot picks. Part of the scenario; the web UI can replace it. | Impatient user who taps quickly and never reads |
| **Step** | One action on the app: tap, type, swipe. Looking at the screen and waiting do not count. | Tap Next |
| **Segment** | One bot session of up to 10 steps. A run is split into segments so the bot's context stays small; each gets the goal and a short summary of the earlier ones. | A 30-step run is 3 segments of 10 |

A scenario (with its persona) defines a run; the run executes as segments; each segment is a
series of steps. A run ends when the steps run out, the goal's "Done when" is met, or the bot
is stuck, so `10 / 15` steps with "goal reached" is a finished run.

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
are listed on the left, with a count of the rest in `runs/`. Each has a
**Copy ID** button that copies the run's folder name in `runs/` (for example
`2026-10-04-025211-medstime-autonomous-add-medication`), so you can paste it
to Claude Code and it opens the whole run: logs, prompts, and screenshots.
**Clear** (when no run is in progress) empties the page and resets the form to
its defaults. It deletes only `runs/latest.json`, the copy of the last run's
`status.json` that the page reads; the run's folder stays, and the run is
still listed with its report.

**Finding history** (`/history`) lists every finding from every run, filterable
by severity, app, scenario, and text, with the bot's own failures hidden by
default. Selecting one shows its details, screenshot, the steps that led to it,
and a link to its run's report. The server listens on localhost only.

### Terminal

```
python3 scripts/explore.py medstime onboarding
python3 scripts/explore.py medstime autonomous --steps 40
python3 scripts/explore.py medstime autonomous --steps 40 --goal "Add a medication, then edit it"
python3 scripts/explore.py medstime autonomous --model gpt-6-sol --report-model gpt-6-sol
python3 scripts/explore.py medstime autonomous-medication-lifecycle --model claude-sonnet-5-5:no-thinking
```

`--steps` overrides the scenario's step budget. `--goal` replaces the
scenario's goal and makes the run open-ended: the bot explores until the steps
run out. `--persona` replaces the scenario's persona. `--model` runs the bot on
another model (Haiku 4.5 by default; any `gpt-*` model goes through Codex), and
`--effort` sets `low` or `medium`. `--report-model` picks who writes the report:
`claude-sonnet-5-5` (default), `claude-opus-5-5`, or `gpt-6-sol`, always at low
effort. A Claude model with `:no-thinking` (`claude-haiku-4-5:no-thinking`,
`claude-sonnet-5-5:no-thinking`, `claude-opus-5-5:no-thinking`) runs without extended
thinking and without effort; the web UI lists them under "No thinking".

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
| `segments.jsonl` | One line per segment: status, summary, steps, screenshots taken, cost |
| `status.json` | Live progress for the web UI (also copied to `runs/latest.json`) |
| `run.json` | The resolved app config and scenario |
| `screenshots/` | One per finding, taken while the problem was on screen, saved from the segment log; other screenshots are not kept |
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
- **Swipes**: `swipe` scrolls a container and runs through its middle, and
  MobileBuildMCP offers it only on scroll containers, never on a list row. To
  reveal a row's swipe actions (Delete, Archive), the bot uses `drag` on the
  row's own text, image, or button, which starts on that element. Without it,
  a row swipe landed in the middle of the list, below the row.
- **Covered controls**: MobileBuildMCP's `touch` taps the middle of an
  element without checking what is there, so a control under a fixed bar (a
  Next button, the keyboard) gave its tap to the bar. The bot taps with
  `safe_tap` from `scripts/probe_tools.py` instead (see below), and keeps
  `touch` only for elements with neither label nor value.
- **Taps**: the bot taps with a 0.15 s touch (a scenario can set another with
  `tapDelay`), and focuses a text field and
  checks for the keyboard before typing. Short taps were often ignored, and
  typing into an unfocused field is silently lost.
- **Screenshots**: the bot takes them with `returnFormat: "base64"`, so the
  image comes back to the model and it actually sees the screen (with `path`
  it only got a file path it could not open). It takes at most two per
  segment by default (`SCREENSHOT_LIMIT` in `explore.py`; a scenario can set
  `screenshotLimit`), since every image stays in
  its context for the rest of the segment: when a tap had no effect or opened
  an unexpected screen, when something looks wrong, and for the purple error
  popup. It refers to them by number (1, 2, ...); `explore.py` takes those images
  from the segment log (Claude's tool results or Codex's MCP results), saves
  the ones a step or finding names into `screenshots/`, then removes all image
  data from the log and deletes the copies Claude Code keeps under
  `~/.claude/projects/.../<session>/tool-results/`. A finding needs a
  screenshot unless all are used and none shows the problem.
- **Covered controls**: the snapshot lists a control even when a fixed
  button, bar, keyboard, or sheet covers it, or the screen edge cuts it off;
  a tap there hits what is on top. The bot scrolls such a control into the
  open first, and when a tap has no effect or opens an unexpected screen it
  checks a screenshot for this before it reports anything.
- **Paywalls**: the bot buys a plan; the purchase sheet is a test environment
  (local StoreKit, or the sandbox Apple Account signed in on the simulator under
  Settings → Developer), so nothing is charged. Sandbox purchases stay on that
  account across reinstalls until the subscription lapses. The bot never taps
  Cancel Subscription or Manage Subscriptions: they open Apple's App Store
  sheet, which cannot load a mock-store purchase. It never signs in to an Apple
  Account and reports a finding if asked to.
- **Permissions**: the bot always allows notifications and skips alarms; a
  scenario with `allowAlarms: true` makes it allow alarms too.
- **Settings is off limits**: the bot never opens the iOS Settings app or
  presses Home. If another app comes to the front anyway, it taps "◀ <app>"
  in the status bar. When the snapshot does not list that link, it ends the
  segment with status `left_app`, and `explore.py` relaunches the app with its
  launch arguments and starts the next segment (after two such relaunches in a
  row with no steps, the run ends as stuck). The bot has no launch tool, so the
  app always runs with `app.md`'s `launchArgs` (`-mock-store`, `-hide-debug-tab`):
  no Debug tab, and purchases through the mock store.

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
| `launchArgs` | Optional launch arguments, for example `["-reset-onboarding"]`; added after the app's own `launchArgs` from `app.md` (MedsTime: `-mock-store`, so purchases need no App Store account) |
| `thinking` | `"off"` runs a Claude bot without extended thinking (`MAX_THINKING_TOKENS=0`), for fast runs such as Autonomous - Fast random taps (`autonomous-fast`); a `:no-thinking` model does the same for one run |
| `skipOnboarding` | `true` writes the app's `skipOnboardingDefaults` (from `app.md`) into its UserDefaults after install, so it opens past onboarding |
| `allowAlarms` | `true` makes the bot allow alarms as well as notifications, in onboarding and on the system alerts; by default it skips alarms. Used by Autonomous - Full app, permissions allowed (`autonomous-full-app`) |
| `model` | Bot model for this scenario, for example `claude-sonnet-5-5`; default Haiku 4.5. The web UI preselects it, and `--model` or another choice in the UI replaces it |
| `reportModel` | Model that writes the report, one of `claude-sonnet-5-5`, `claude-opus-5-5`, `gpt-6-sol`; default Sonnet 5.5. `--report-model` or the UI replaces it |
| `tapDelay` | Touch length of a tap in seconds; default `0.15`. `autonomous-full-app` uses `0.165` |
| `screenshotLimit` | Screenshots the bot may take per segment; default `2`. More screenshots let it document more findings, but each stays in its context for the rest of the segment. `mm-030` uses `3` |

The body has `## Goal`, `## Persona`, and an optional `## Done when`. Leave out
`Done when` for open-ended exploration.

## safe_tap (`scripts/probe_tools.py`)

A second MCP server in `.mcp.json` (`probe-tools`), standard library only,
with one tool. `safe_tap` takes a control's label (plus `index` and
`elementType` when several match), hit-tests the control's middle with AXe
(`describe-ui --point`), and taps only where the control itself is on top.
If something covers it, it drags the content clear of the cover, slowly so
it does not fling, and checks again, up to 3 times; then it reports what
covers the control instead of tapping. It also skips the top 50 and bottom
34 points, where iOS keeps touches for its own gestures. It returns text,
so the bot calls `snapshot_ui` next. A tap takes about 1–2 s, or about 5 s
with scrolling.

AXe is `$AXE_PATH` if set, else the copy bundled with the MobileBuildMCP
version `.mcp.json` pins, from the npx cache; the simulator is the one in
`.mobilebuildmcp/config.yaml`, which `explore.py` writes for every run. Try it
by hand on the current screen:

```
python3 scripts/probe_tools.py --tap "Decrement"
```

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
`xcode-select -p`, into `.build/DerivedData` (not committed). It skips the build when the
app repo's commit, uncommitted changes, and untracked files hash the same as at
the last successful build (`.build/fingerprints.json`), and installs the
existing `.app`. No Xcode agent
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
