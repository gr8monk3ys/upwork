# Pilot Friction Log — 2026-05-09

**Spec:** docs/superpowers/specs/2026-05-09-pilot-design.md
**Plan:** docs/superpowers/plans/2026-05-09-pilot-execution.md
**Pilot started:** 19:38 PDT
**Pilot ended:** _(in progress)_

## Summary

| Severity | Count |
|---|---|
| blocker | 0 |
| annoyance | 0 |
| nit | 0 |

(Updated at end of pilot.)

## Entries

### F-01: README assumes Upwork API app credentials but doesn't help get them
- **Step:** Pre-flight — obtaining Upwork API app credentials before `upwork config setup`
- **Expected:** README would mention what to put in the Upwork API application form, or link to a snippet that's known to be accepted, since this is the first real on-ramp step.
- **Observed:** User reached the Upwork developer keys application page and got stuck on the "describe how you'll use the API" question. Had to ask for help mid-pilot. README simply links to `upwork.com/developer/keys/apply` without context.
- **Severity:** annoyance (it would be `nit` for someone who has API experience, but for first-time use it's enough friction to break flow)
- **Quote/screenshot:** README line 40: "An Upwork API application (Client ID + Client Secret)" — no further guidance.
- **Hypothesis:** Add a "What to put on the API application form" section or link in the README, ideally with a copy/pasteable description that's ToS-safe (no proposal submission, single-user, etc.). Also a candidate for a setup wizard that surfaces this *before* asking for credentials.

### F-02: No clear guidance that secrets go directly into the wizard, not into chat
- **Step:** Pre-flight — obtaining and providing Client Secret
- **Expected:** Tool/README would tell the user "paste your secret into the setup wizard's prompt; never share it in chat or commit it." User would understand the boundary before it's too late.
- **Observed:** User pasted Client ID + Client Secret directly into the chat with the assistant, expecting that's how they'd be handed over. Had no mental model that secrets enter the system through the wizard's no-echo prompt and never need to leave their terminal.
- **Severity:** annoyance (genuine security boundary unclear; lucky no real compromise yet but exact path that leads to leaking secrets to logs / shared screenshots / training data)
- **Quote/screenshot:** _(redacted — actual values must not appear in this log)_
- **Hypothesis:**
  - The setup wizard could print a one-line banner before the secret prompt: "Paste your Client Secret here. The terminal will not echo it; it goes straight to your OS keychain. Do not share it elsewhere."
  - The README's "Quick Start" could add a single sentence: "When the wizard prompts for secrets, paste them directly — they go to your OS keychain, not to any external service or chat assistant."
  - Counts as evidence for an on-ramp redesign (option C from brainstorming).
