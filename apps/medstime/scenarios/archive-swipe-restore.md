---
name: Archive and restore with a swipe
freshStart: true
skipOnboarding: true
maxSteps: 30
model: claude-haiku-4-5
reportModel: claude-sonnet-5-5
---

## Goal

Onboarding is skipped: the app opens on the Schedule tab. If a paywall
appears, buy the subscription. Add a medication, archive it from its details
screen, then go to the Medications tab and restore it by swiping its row in
Archived Medications. Do not use the Unarchive button in the details screen.
Afterwards check that the medication is back under Current Medications and
its doses are back on the Schedule.

Along the way, look for inconsistencies (the list, the details, and the
Schedule disagreeing, or text that does not match what happened), wrong
behavior (a control that does nothing or does the wrong thing), and bugs.

## Done when

The medication was restored with a swipe on its row, and it is back under
Current Medications and on the Schedule.

## Persona

Organized user who keeps the medication list tidy, not tech-savvy.
