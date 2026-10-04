---
name: Screen - Schedule tab
freshStart: true
skipOnboarding: true
maxSteps: 50
model: claude-sonnet-5-5
reportModel: claude-opus-5-5
---

## Goal

Onboarding is skipped: the app opens on the Schedule tab. If a paywall
appears, buy the subscription.

Setup, once: add three medications with + so the Schedule has something to
show. Give two of them the same time today, so they form a group card, and
the third a different time; make one of them repeat on specific days of the
week. After that, stay on the Schedule tab and the sheets it opens until the
step budget runs out. Do not go to another tab.

Test the Schedule in depth:
- move between days with the arrows and the date picker (Schedule Date),
  Today, past days, and days far ahead,
- the Scheduled, Taken, and Skipped filter,
- open and close group cards; log one medication of a group, then the rest,
  and Log all as Taken,
- log doses as Taken and Skipped, edit a logged dose, change its time and
  amount,
- tap a dose on a future day and read the message,
- check each day against the medications' frequencies: a medication on
  Monday and Friday must appear only on those days.

Look for inconsistencies (a dose on the wrong day or at the wrong time, a
group summary or status that does not match its rows, a filter that shows
the wrong doses, a count that does not add up), wrong behavior (a log that
is not saved, a card that does not open, a message that does not match the
day), and bugs (crashes, frozen screens, overlapping or cut-off text).

## Persona

Careful tester who checks every day and every status against what was set
up.
