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
# Optional: pin an exact simulator by UDID (`xcrun simctl list devices`).
# simulatorId:
---

Medication reminder app. Users add medications with doses and times, get
alarms and notifications, track intake, and export a PDF history. Data can sync
through iCloud. Premium features sit behind a subscription paywall.

## Notes for the bot

- First launch shows onboarding: three welcome pages, then iCloud, alarms, and
  notifications screens. A paywall may follow.
- The UI is dark mode only.
- Use made-up medication names and doses, never real personal data.

## Launch arguments

Debug builds only.

- `-reset-onboarding`: show onboarding again without reinstalling.
