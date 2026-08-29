# Profile Ship Checklist

Goal: the profile is LIVE on Upwork and the first 10 real proposals are sent.
Everything here is manual Upwork-UI work — the CLI can't do it for you, and
browser automation of Upwork violates their ToS (account suspension risk), so
don't script any of this.

Source of truth for all copy: `profile-packet.md`. Fill every `[FILL]` there
first; nothing ships with a placeholder.

## Phase 1 — Facts & links (~1 hour, do before touching Upwork)

- [ ] Fill every `[FILL]` in `profile-packet.md` with real numbers/facts
- [ ] Verify each link loads (dead Vercel deployments are common):
  - [ ] https://blog-ai-beta-eight.vercel.app
  - [ ] https://link-flame-rouge.vercel.app
  - [ ] https://infini-star.vercel.app
  - [ ] https://lscaturchio.xyz
  - [ ] Each GitHub repo you'll link: README presentable, no dead badges
- [ ] Take 1–3 screenshots per portfolio item you're shipping (5–6 items)
- [ ] Pick/confirm a professional headshot

## Phase 2 — Paste the profile (~1 hour, Upwork Settings → Profile)

- [ ] Title (from packet §1)
- [ ] Overview (packet §2 — no external links in the text)
- [ ] Hourly rate: $95 (packet §3)
- [ ] Skills: the 15 in packet §4, in order
- [ ] Portfolio: strongest 5–6 items with screenshots + metrics (packet §5)
- [ ] Employment history (packet §7 — no SPS here)
- [ ] Education & certifications (packet §8)
- [ ] Availability badge ON, 30+ hrs/week; profile Public (packet §9)
- [ ] Project Catalog: create catalog A (RAG chatbot) and B (Full-Stack MVP)
      from packet §6; add C later

## Phase 3 — Prove the pipeline works (~30 min, uses the CLI)

- [ ] `upwork config setup` — walk OAuth. If Upwork API access is denied or
      stalls, log it and continue: the CLI still drafts via
      `propose generate --from-file`, which needs no API.
- [ ] `upwork config profile --file docs/profile/profile-packet.md`
- [ ] Run the dogfood pilot (docs/superpowers/specs/2026-05-09-pilot-design.md)
      and actually write entries into the friction log this time. If the API
      path is blocked, pilot the manual loop instead:
      browse Upwork → copy a job posting into `job.md` →
      `upwork propose generate --from-file job.md` → edit → submit by hand.

## Phase 4 — First 10 proposals (the only phase that wins contracts)

- [ ] Send 2 proposals/day for 5 days. For each:
  - [ ] Job posted <24h ago, <15 proposals, payment-verified client
  - [ ] Draft with the CLI, then personalize the first two sentences by hand
  - [ ] Submit on Upwork, then `upwork pipeline move <job-id> applied`
- [ ] Answer every client reply within 4 waking hours
- [ ] After each outcome: `upwork propose mark <id> won|lost|no_response`
- [ ] After the first win: `upwork propose learn` to build the style guide
- [ ] After 10 sent: review `upwork pipeline stats` and adjust (rate, niches,
      proposal style) based on actual response rate

## Explicitly not on this list

- More CLI features, CI work, or repo polish — frozen until Phase 4 is done
- Any scripted interaction with upwork.com (scraping, auto-apply) — ToS
  violation, and losing the account loses everything above
