---
name: Autonomous - Bug hunt
freshStart: true
maxSteps: 60
---

## Goal

Get through onboarding (buy the subscription on the paywall), then try to
cause a bug by doing the app's actions in random, unusual orders:
- add medications with odd inputs, then abandon Add Medication halfway,
- edit, delete, archive, and unarchive medications in surprising sequences,
- mark doses taken or skipped, undo, then change or delete that medication,
- jump between days in the schedule and add or change medications there,
- change Settings values, then go back and check the schedule and list,
- tap quickly, go back mid-flow, reopen sheets, switch tabs in the middle.
Pick each next action at random and do not repeat the same flow twice. After
each change, check that the Medications list, the Schedule, and the counters
agree.

## Persona

Impatient, chaotic user who taps around, not tech-savvy.
