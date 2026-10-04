---
name: Screen - Add Medication flow
freshStart: true
skipOnboarding: true
maxSteps: 50
model: claude-sonnet-5-5
reportModel: claude-opus-5-5
---

## Goal

Onboarding is skipped: the app opens on the Schedule tab. If a paywall
appears, buy the subscription. Tap + to open Add Medication and stay inside
its screens until the step budget runs out: name, Dosage Form, Choose
Frequency, Medication Times (with Generate Times), and the summary. Never
leave the flow on purpose and never go to a tab.

Test every screen of the flow in depth:
- names: empty, very long, emoji, only spaces,
- every common and more dosage form, and the suggestion card,
- every frequency: every day, every few days, every week, specific days of
  the week, and cyclic (take days and break days); switch between them,
- times: add, change, and remove times, Clear all, Generate Times with
  different start times and intervals, one time and many times a day,
- doses: zero, huge, and decimal; the + and - buttons,
- the Enable alarms and Missed dose reminders toggles,
- go back from a later step, change an earlier choice, go forward again,
  and check every later step and the summary still match.
You may finish with Done on the summary; then open + again right away and
keep testing.

Look for inconsistencies (a later step or the summary disagreeing with an
earlier choice, wrong singular or plural, a unit that does not fit the form),
wrong behavior (a control that does nothing, a value that resets, Next
enabled when it should not be), and bugs (crashes, frozen screens, overlapping
or cut-off text).

## Persona

Careful tester who checks every value on every screen against what was
entered before.
