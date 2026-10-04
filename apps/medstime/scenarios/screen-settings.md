---
name: Screen - Settings tab
freshStart: true
skipOnboarding: true
maxSteps: 50
model: claude-sonnet-5-5
reportModel: claude-opus-5-5
---

## Goal

Onboarding is skipped: the app opens on the Schedule tab. If a paywall
appears, buy the subscription.

Setup, once: add one medication with +, so Delete All Data has something to
delete. After that, go to the Settings tab and stay on it and the screens it
opens until the step budget runs out. Do not go to another tab.

Test the Settings tab in depth:
- Notification Permission and Alarm Permission: Allow Notifications and
  Allow Alarms, and the system alerts they bring up,
- Missed Dose Notification Display, Time-Sensitive Notification Display,
  and Alarm Display: open each, change it, and change it back,
- Touch Feedback, iCloud Backup, Subscription, Legal Information,
- Restore Purchases (allowed in this scenario),
- Delete All Data only in your last few steps: try No first, then Yes, and
  check the medication is gone.

Never tap Manage Alarms, Manage Notifications, Open iPhone Settings,
Cancel Subscription, Manage Subscriptions, Rate us, Contact us, or Share. If
you open Privacy Policy or Terms of Service, close it right away with the X
button. If another app comes to the front, go back with the "◀ MedsTime" link
in the top-left corner.

Look for inconsistencies (a status that does not match the permission you
gave, a value that differs after you leave and come back, text that does not
match what happened), wrong behavior (a toggle or row that does nothing, a
change that is not kept), and bugs (crashes, frozen screens, overlapping or
cut-off text).

## Persona

Curious user who pokes at every option and checks it stays changed.
