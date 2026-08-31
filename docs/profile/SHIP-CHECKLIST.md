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

## Phase 2 — Update the profile (applied live 2026-08-31, authorized session)

- [x] Title (packet §1) — live
- [x] Overview (packet §2; `<200 ms` had to become "under 200 ms": Upwork
      rejects `<` as HTML) — live
- [ ] Hourly rate → $75 (packet §3). **Blocked for automation** (money field);
      Profile → pencil next to $50.00/hr → 75 → Save. 30 seconds.
- [x] Skills: 20 live (packet §4)
- [x] Portfolio: TAlker (+GitHub link), InfiniStar, Sizzle diagram added;
      Blog-AI, Link Flame, Remedi, HealthCalc, Paper Summarizer, Personal
      Website were already there. Upwork's link fetcher rejects Vercel URLs,
      so InfiniStar/Link Flame carry no link.
- [x] Employment history: Sizzle rewritten with resume numbers, end date
      May 2025; JGI end date Aug 2021; VICE Lab left as-is
- [x] Education & certifications were already correct
- [ ] Specialized profiles A and B (packet §9) — not done
- [x] Availability badge ON, 30+ hrs/week; Rising Talent badge showing
- [x] Project Catalog A (RAG chatbot, $1,500/$3,500/$6,500): gallery image,
      2 client requirements, summary, 4 delivery steps, 1 FAQ added and
      **submitted for Upwork review** 2026-08-31 (user authorized the ToS
      tick). B (MVP) and C (ETL) drafts from Feb 2026 still need the same
      gallery/requirements/description pass and a submit — same wizard,
      ~10 minutes each.

## Phase 3 — Upwork API (optional; do not block on it)

- [ ] `upwork config setup` — walk OAuth. If Upwork API access is denied or
      stalls, log it and move on: `propose generate --from-file` needs no API,
      and it is the path the samples were produced with.
- [ ] If OAuth works: `upwork jobs searches` runs the six saved searches
      already in `settings.yaml`; `upwork jobs score` ranks the results
      against the profile.

## Phase 4 — First 10 proposals (the only phase that wins contracts)

Apply only to jobs that pass every row of packet §11. Two a day for five days:

- [x] 2026-08-31: two real postings found, drafted and staged in the Upwork
      Apply form (`proposals-2026-08-31.md`) — the user clicks Send. Market
      note: with payment-verified + <15 proposals + ≥$50/hr or ≥$1K, the
      RAG/LangChain/FastAPI searches returned under 10 live jobs that day;
      loosen to <20 proposals before loosening budget.

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
