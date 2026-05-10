# Dogfood Pilot — `upwork-cli` Daily-Use Friction Discovery

**Status:** Approved design. Ready for implementation plan.
**Date:** 2026-05-09
**Author context:** Brainstorming session synthesis. Repo owner is the sole user; goal is "daily-use polish for myself."

## Problem

`upwork-cli` is a substantial, well-tested Python tool with six command groups, AI integration, and active recent development. The owner has not yet adopted it as a daily driver — not for any specific identified reason, but because they "haven't really tried." Without real-usage signal, any feature work risks polishing things the owner will never touch.

## Goal

Produce concrete, ranked evidence about where `upwork-cli` actually breaks, confuses, or under-delivers in a real morning-routine workflow — so the next design round attacks evidence, not speculation.

## Success criterion

A `pilot-friction-log.md` checked into the repo, containing 0+ entries each tagged severity (blocker / annoyance / nit), with enough specificity that the next design session can prioritize fixes immediately.

A "0 entries" outcome is legitimate and useful: it means ship as-is and turn to other work.

## Non-goals

- Validating that the tool is "good." We are measuring friction, not approving the product.
- Building any new features during the pilot.
- Testing every command. The pilot covers the core morning loop only.
- Sending real proposals to real Upwork clients.

## Pre-flight conditions (confirmed met)

- Upwork API app credentials (Client ID + Client Secret)
- Anthropic API key
- Active Upwork account that returns real search results
- 30-45 min focused time

If any condition becomes false at runtime, the pilot pivots: missing condition becomes the first friction-log entry rather than a blocker for the whole exercise.

## The pilot scenario

The narrative under test: *"It's morning. I open my terminal. I want to find one good Upwork job and have a proposal ready in 15 minutes."*

The 15-minute target is the *user's in-narrative goal* — it makes friction visible by being tight. The pilot itself takes longer (the 30–45 min budgeted in pre-flight) because we pause between steps to capture observations.

**The path:**

1. **Setup** — `upwork config setup`. Walk OAuth flow.
2. **Profile import** — `upwork config profile --file upwork-profile-draft`.
3. **Search** — `upwork jobs search "<keyword from upwork-profile-packet>"`.
4. **Score** — `upwork jobs score`.
5. **Inspect top result** — `upwork jobs detail <id>` for the highest-scored job.
6. **Generate proposal** — `upwork propose generate <id>`.
7. *(Optional)* **Refine** — `upwork propose refine --feedback "..."` once.
8. *(Optional)* **Save to pipeline** — `upwork pipeline move <id> applied`.

**Stopping rule:** On a hard blocker (e.g., OAuth fails completely), stop, log it, and that becomes the entire finding. Do not push past blockers — fighting through hides real friction.

## Capture protocol

### Location

`docs/superpowers/specs/2026-05-09-pilot-friction-log.md` — created during the pilot, committed at the end.

### Entry shape

```markdown
### F-NN: <short title>
- **Step:** <which command/step>
- **Expected:** <what we thought would happen>
- **Observed:** <what actually happened>
- **Severity:** blocker | annoyance | nit
- **Quote/screenshot:** <error text, output snippet, or link>
- **Hypothesis:** <if obvious; otherwise leave blank>
```

### Severity rubric

| Tag | Meaning |
|---|---|
| **blocker** | I cannot continue the morning routine without intervention. |
| **annoyance** | I can continue but I'm thinking about quitting / opening a different tab. |
| **nit** | Briefly noticed, didn't slow me down, worth fixing if cheap. |

### What we log even when nothing breaks

- AI output quality. Does the score reasoning convince? Does the proposal sound like the user's voice?
- Time-to-first-useful-output for each step.
- Any time the user verbalizes "wait, why does it…" — those are friction events even if nothing technically broke.

## Decision criteria — what to do with the log

| Result | Next step |
|---|---|
| 0–2 friction points, no blockers | Ship as-is. Pivot to other work. |
| 3–5 friction points OR any blocker | Design fixes for them in a follow-up brainstorming. |
| 6+ friction points OR multiple blockers | Density signals the right unit of work is "redesign the on-ramp" or "redesign the daily flow," not point fixes. Pick based on where the density clusters. |

## Roles during the pilot

**User:**
- Drives the keyboard. Runs each command.
- Narrates when something feels off, even briefly.
- Does *not* try to fix problems mid-flight — that biases the data.

**Claude:**
- Keeps the friction log open and writes entries as the pilot proceeds.
- Suggests next commands only when the path is genuinely ambiguous.
- Does *not* make code changes during the pilot. Changes happen *after* evidence is in.

## Out of scope for this pilot

- Edge-case commands (`offers withdraw`, `messages send`, `earnings export`).
- Trying every tone/length combination of `propose generate` — one pass.
- Optimizing AI prompts mid-pilot.
- CI / infra / non-user-facing code.
- Sending real proposals to real Upwork clients.

## Implementation outline

The implementation plan (next phase, via the writing-plans skill) should structure the pilot as a sequence of discrete steps with clear pause points between them. Each step's plan entry needs:

1. The exact command(s) to run.
2. The expected outcome (what "this worked" looks like).
3. The friction signals to watch for at this step specifically.
4. The decision rule for moving forward (proceed / log and proceed / log and stop).

Everything in this spec is a constraint on what that plan produces. The plan does not introduce new scope; it sequences the execution.
