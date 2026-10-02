---
name: MedsTime
projectPath: /Users/vladimir/Projects/medstime-ios/MedsTime.xcodeproj
scheme: MedsTime
configuration: Debug
bundleId: com.violetsoft.MedMate
simulatorName: iPhone 17 Pro
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
