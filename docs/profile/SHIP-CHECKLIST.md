# Profile Ship Checklist

Goal: the updated profile is LIVE on Upwork and the first 10 real proposals
are sent. Everything in Phase 2 and Phase 4 is manual Upwork-UI work — the CLI
can't do it, and browser automation of upwork.com violates their ToS (account
suspension risk, and the account carries a 98% JSS you cannot rebuild), so
don't script any of it.

Source of truth for all copy: `profile-packet.md`. `profile.yaml` is the same
content in the shape the CLI imports.

## Phase 1 — Facts & links (DONE 2026-08-31)

- [x] Every `[FILL]` in `profile-packet.md` replaced with a verified fact
      (resume source, repo READMEs, live Lighthouse runs). No placeholders remain.
- [x] Timeline made consistent with the resume: "6 years / since 2020",
      Sizzle + JGI + freelance, USC MS + UC Merced BS. The old "8+ years since
      2017" is gone.
- [x] Links verified (all HTTP 200 on 2026-08-31):
  - [x] https://blog-ai.vivancedata.com (the canonical Blog AI URL; the old
        `blog-ai-beta-eight.vercel.app` also loads but don't use it)
  - [x] https://link-flame-rouge.vercel.app
  - [x] https://infini-star.vercel.app
  - [x] https://lscaturchio.xyz
  - [x] GitHub: blog-AI, link-flame, TAlker, huggingface, trading-bot,
        resume-AI are public. InfiniStar, homelab, fraud-stream are PRIVATE —
        described in the packet, never linked.
- [x] Lighthouse numbers recorded in `lighthouse-2026-08-31.md`
- [x] `profile.yaml` imported into the CLI (`upwork config profile --file docs/profile/profile.yaml`)
- [x] Drafting pipeline proven end-to-end on three sample jobs —
      `proposal-samples.md`
- [x] Screenshots captured 2026-08-31 into `docs/profile/assets/` (1440×900):
      `blog-ai-live.png` + `blog-ai-repo.png`, `link-flame-live.png`,
      `infinistar-live.png`, `talker-hero.png`,
      `sizzle-vision-pipeline.png` (schematic diagram drawn from the resume
      bullets — nothing beyond them).
- [x] Headshot: `docs/profile/assets/headshot.webp` (1200×1244, from
      lscaturchio.xyz). Upwork wants JPG/PNG — convert on upload if it
      refuses WebP.

## Phase 1b — Fix the Anthropic key (5 min, blocks every AI command)

The key in the system keychain returns `401 authentication_error` from the
API directly (checked 2026-08-31). The three sample drafts were generated
with a key passed as `ANTHROPIC_API_KEY` for that session only; nothing was
written to the keychain.

- [ ] `upwork config setup` → paste a working key when prompted for Anthropic
      (Enter keeps the dead one — don't). Or `export ANTHROPIC_API_KEY=...` in
      the shell; env wins over keychain.
- [ ] Prove it: copy one job block from `proposal-samples.md` into `job.md`
      and run `upwork propose generate --from-file job.md`. A draft appearing
      means it's fixed. (`config status` saying "Set" proves nothing — it only
      checks presence; see friction log F-01.)

## Phase 2 — Paste the profile (~1 hour, Upwork Settings → Profile)

This is an UPDATE of the existing profile, in this order:

- [ ] Title (packet §1)
- [ ] Overview (packet §2 — no external links in the text)
- [ ] Hourly rate: $95 (packet §3)
- [ ] Skills: the 15 in packet §4, in order; use the swap list if a label
      isn't accepted
- [ ] Portfolio: items 1–5 from packet §5 with screenshots + the number in
      each; add 6–10 later
- [ ] Employment history: Sizzle, Freelance, JGI exactly as packet §7
- [ ] Education & certifications (packet §8)
- [ ] Specialized profiles A and B (packet §9)
- [ ] Availability badge ON, 30+ hrs/week; profile Public (packet §10)
- [ ] Project Catalog: create A (RAG chatbot) and B (Full-Stack MVP) from
      packet §6; add C later

## Phase 3 — Upwork API (optional; do not block on it)

- [ ] `upwork config setup` — walk OAuth. If Upwork API access is denied or
      stalls, log it and move on: `propose generate --from-file` needs no API,
      and it is the path the samples were produced with.
- [ ] If OAuth works: `upwork jobs searches` runs the six saved searches
      already in `settings.yaml`; `upwork jobs score` ranks the results
      against the profile.

## Phase 4 — First 10 proposals (the only phase that wins contracts)

Apply only to jobs that pass every row of packet §11. Two a day for five days:

- [ ] For each job: copy the posting into `job.md` →
      `upwork propose generate --from-file job.md` → rewrite the first two
      sentences by hand per packet §12 → submit on Upwork →
      `upwork pipeline move <manual-id> applied` (the CLI prints the id)
- [ ] Answer every client reply within 4 waking hours
- [ ] After each outcome: `upwork propose mark <id> won|lost|no_response`
- [ ] After the first win: `upwork propose learn` to build the style guide
- [ ] After 10 sent: `upwork pipeline stats`; adjust rate, niches, or
      proposal style from the actual response rate, not from a hunch

## Explicitly not on this list

- More CLI features, CI work, or repo polish — frozen until Phase 4 is done
- Any scripted interaction with upwork.com (scraping, auto-apply, or
  "just reading the profile page" through a browser extension) — ToS
  violation, and losing the account loses the JSS
