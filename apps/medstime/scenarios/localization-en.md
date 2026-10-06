---
name: Localization EN - Translations, forms, plurals, and the Home day summary (English)
freshStart: true
allowAlarms: true
# Starts the app in English whatever the simulator's language is:
# -AppleLanguages picks the app's localization, -AppleLocale the number and plural rules.
launchArgs: ["-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
model: claude-sonnet-5-5
reportModel: claude-sonnet-5-5
# Estimated 185 steps (onboarding and purchase 15, categories and forms 40, seven medications
# 80, logging and the day summary 40, Settings 5, cross-checks 5); 200 leaves little room.
maxSteps: 200
# One more screenshot per segment than the default 2, for the many label checks.
screenshotLimit: 3
---

## Goal

The app runs in English. Recent changes renamed medication categories and section headers,
replaced the word "preparation" with "medicine", added a category for medications without a
specific form, changed the paywall discount caption, and made the day summary under the date on
the Schedule tab show only taken and skipped counts. Use the app like a native English speaker,
cover the test data below, and report everything that reads wrong. Work out what you see
yourself; the rules below say what is correct, not what every screen reads.

### About the app

- Onboarding is a few welcome pages, then permission screens and a paywall with a monthly and a
  three-month plan; the three-month plan shows its discount in percent.
- Add Medication is a series of steps: name, medication type, dose, times, and a summary with an
  optional instructions field. The medication-type screen lists categories in sections; a
  category opens a form screen with general and more specific forms, unless it has no forms.
- The Schedule tab shows today's medications by time. Medications at the same time form a group
  with a summary line naming their forms. Under the date is a line with the day's counts.
  Medications are logged as taken or skipped from their row or for a whole group.
- Tabs: Schedule, Medications, Settings.

### Rules of correct behavior

- All app text is English.
- Every count agrees with its word ("1 medicine", "2 medicines", "1 tablet", "2 tablets").
- The day summary line shows taken and skipped counts only, never a "not logged" count, and its
  counts always match the rows of that day marked taken and skipped.
- The group summary names each medication by its general form. A medication without a specific
  form ("Medicine") is never named beside other forms: it is counted instead ("1 more"), and a
  group of only such medications shows their count ("2 medicines").
- The route categories read by the route alone (Oral, Rectal, Vaginal); their general rows and
  summary words use "medicine". The word "preparation" appears nowhere.
- No category named Pack or Other exists.
- The paywall discount is a correctly formatted percentage in a natural sentence.

### Intended, not findings

- "Medicine" sits alone in the last section of the type screen and has no forms: tapping it
  selects it, like Ampoule and Infusion.
- Row statuses ("Taken", "Skipped", "Not logged") on individual rows are expected; only the day
  summary line drops "not logged".
- Rows in an expanded group show name and status only, with no dose.

### Test data

Go through onboarding, allow notifications and alarms (app screens and system alerts), read the
paywall, and buy the monthly plan.

Look through the type screen and open the Oral, Rectal, and Vaginal categories and one category
with several general forms. Then add seven daily medications with made-up names, setting times
with `turn_wheel` and checking the time button:
- 08:00: two medications of the Medicine category.
- 09:00: a tablet (general row) and an oral medication (general row).
- 10:00: a tablet with a specific form (2 tablets), drops, and one Medicine.

On the Schedule tab, read the group summaries, then log in varied ways and read the day summary
after every change: take and skip single medications (expand a group), log a whole group as
taken, change a logged medication from taken to skipped and back, and open another day and come
back.

Finally look through Settings (without tapping anything listed under Rules) and the Medications
tab.

### Always watch

On every screen, read all text and report anything inconsistent, even if no rule above mentions
it: a raw key (`medication-...`, `paywall-...`, `onboarding-...`), a format code (`%@`, `%lld`,
`%%`), a blank label or placeholder icon, Serbian text, a wrong singular or plural, a count that
does not match the screen, the same thing named differently in two places, or grammar,
capitalization, or wording a native speaker would find wrong or odd.

### Rules

Strictly never tap these, anywhere:
- Open iPhone Settings, Open Settings, Manage Alarms, Manage Notifications,
- Cancel Subscription, Manage Subscriptions, Restore Purchases,
- Rate us, Contact us, Share, Print, Delete Data.
Never leave the app and never press Home. If another app comes to the front anyway, go straight
back with the "◀ MedsTime" link in the top-left corner. If Privacy Policy or Terms of Service
opens, close it with the X button.

## Done when

Onboarding and the paywall were read, the type screen and the route categories were checked, the
seven medications were added, the group summaries were read, the day summary was read after every
log change, and Settings and Medications were looked through.

## Persona

Careful English-speaking user who reads every label before tapping and notices small wording
mistakes. Not tech-savvy.
