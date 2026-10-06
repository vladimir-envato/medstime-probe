---
name: MedsTime
projectPath: /Users/vladimir/Projects/medstime-ios/MedsTime.xcodeproj
scheme: MedsTime
configuration: Debug
bundleId: com.violetsoft.MedMate
simulatorName: iPhone 17 Pro
# Launch arguments for every run. -mock-store (DEBUG builds) makes purchases succeed without the
# App Store, since the local StoreKit configuration only applies when Xcode launches the app.
# -hide-debug-tab (DEBUG builds) keeps the bot away from the Debug tab's tools.
launchArgs: ["-mock-store", "-hide-debug-tab"]
# UserDefaults that a scenario with skipOnboarding: true writes after install, before launch.
skipOnboardingDefaults: {"onboarding.finished": true}
# Pins the exact simulator by UDID (`xcrun simctl list devices`): iPhone 17 Pro on iOS 26.5.
# Without it, simulatorName picks the newest iOS runtime with that name.
simulatorId: 7B34DDF1-D35D-44A2-A24B-5732C1BB10F0
---

Medication reminder app. Users add medications with doses and times, get
alarms and notifications, track intake, and export a PDF history. Data can sync
through iCloud. Premium features sit behind a subscription paywall.

## Notes for the bot

- First launch shows onboarding: three welcome pages, then iCloud, alarms, and
  notifications screens. A paywall may follow.
- The UI is dark mode only.
- Add Medication steps and the medication summary have a fixed button at the
  bottom (Next or Done) over a scrolling list. Controls lower in the list
  (Add time, the dose + and -, Times) sit under that button until you scroll
  up.
- A medication time (the time button next to each dose on Medication Times)
  opens a small popover with two wheels, hours and minutes in steps of 5.
  Set it with `turn_wheel` (index 0 hours, 1 minutes), then read the time
  from the button's value in the next snapshot. Tap outside the popover, or
  the next control, to close it.
- Use made-up medication names and doses, never real personal data.

## Launch arguments

Debug builds only.

- `-reset-onboarding`: show onboarding again without reinstalling.
