---
name: Screen - Medications tab
freshStart: true
skipOnboarding: true
maxSteps: 50
model: claude-sonnet-5-5
reportModel: claude-opus-5-5
---

## Goal

Onboarding is skipped: the app opens on the Schedule tab. If a paywall
appears, buy the subscription.

Setup, once: add three medications with + that differ in dosage form,
frequency (every day, specific days of the week, cyclic), and times. After
that, go to the Medications tab and stay on it and the screens it opens
(medication details, editing, Print a Schedule, PDF Preview) until the step
budget runs out. Do not go to another tab.

Test the Medications tab in depth:
- open each medication by tapping anywhere on its row,
- in the details, change the name, form, frequency, times, and toggles,
  save, and check the row shows the change,
- archive a medication from its details, then restore it by swiping its row
  in Archived Medications (use drag on the row's text),
- archive every medication, then restore them all, and read the section
  titles and the note under the archived ones,
- the printer button: every schedule period, PDF Preview, and Save on My
  iPhone (never Print),
- delete one medication and check the list.

Look for inconsistencies (a row, its details, and the PDF disagreeing about
name, form, days, or times; a section title that does not match its rows),
wrong behavior (an edit that is not saved, a swipe or tap that does
nothing, a period that should be unavailable but is not), and bugs
(crashes, frozen screens, overlapping or cut-off text).

## Persona

Organized user who keeps the medication list tidy and checks that every
row matches its details.
