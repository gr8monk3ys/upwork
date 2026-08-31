# Upwork Profile Packet (Final — Copy/Paste)

Single source of truth for the Upwork profile. Every fact below was checked on
2026-08-31 against the resume source (`~/code/resume/`), the repos, and the
live deployments. There are no placeholders left. If you change a number here,
change it in the resume too — clients cross-check Upwork against LinkedIn.

**This is an UPDATE, not a launch.** The live profile (checked 2026-08-31)
shows: Rising Talent badge, $700+ total earnings, 4 jobs (3 completed Feb–May
2026 at $50–$500 fixed price, 1 in progress), one 5.0 review, 239 Connects,
**no Job Success Score yet** (JSS needs more completed work). The resume's
"98% JSS, 4 clients since Aug 2022" does not match what Upwork displays, so
the overview does not claim a JSS — Upwork prints the real stats right next
to it.

**Applied live on 2026-08-31 via the user's own Chrome session (authorized
for profile edits only):** title, overview, 20 skills, Sizzle description +
end date (May 2025), JGI end date (Aug 2021), and three new portfolio items
(TAlker with GitHub link, InfiniStar, Sizzle pipeline diagram). Not applied:
hourly rate (permission classifier blocked the money field — set it by hand),
Project Catalog, specialized profiles.

## 0) What changed from the previous packet, and why

| Old claim | Problem | Now |
|---|---|---|
| "8+ years of development experience", freelance since 2017 | Resume timeline starts May 2020 (JGI); BS graduated 2022. A client who checks LinkedIn sees a contradiction. | "6 years" — professional since 2020, with named roles |
| "50+ projects shipped" | Unverifiable; reads as filler | Named projects with numbers |
| "Production Kubernetes homelab running 50+ services" | Repo README says 43 app manifests, not yet proven end-to-end on a live cluster | "K3s homelab: 43 self-hosted app manifests, CI-validated" |
| No employment history except "self-employed" | Hides the strongest proof: Sizzle ML Engineer with production numbers | Sizzle, JGI, and freelance listed with outcomes |
| Google SPS anywhere | Student program | Dropped entirely — USC MS + UC Merced BS replace it |
| No education | Section can't ship empty | USC MS Applied Data Science, UC Merced BS CSE, two 2025 certs |

## 1) Title (keyword-searched by clients; 70-char cap)

Primary:

> AI Engineer | RAG, LLM Apps, LangChain | Python, FastAPI, Next.js

Alternates:

- Full-Stack AI Developer | RAG & LLM Integrations | Python, TypeScript
- AI/ML Engineer | LLM Apps, RAG Chatbots | Python, Next.js, GCP

## 2) Overview (no external links — Upwork strips/flags them)

I build AI-powered applications that make it to production: RAG systems,
LLM integrations, and the full-stack web apps and data pipelines around them.
Six years of professional software work and an M.S. in Applied Data Science
(USC).

What I deliver:

- RAG and LLM systems: document Q&A, chatbots, content generation, multi-provider LLM backends (OpenAI, Anthropic, Gemini), evaluation harnesses so you can measure retrieval quality instead of guessing
- Full-stack web apps: Next.js/React/TypeScript front ends with FastAPI or Node backends, Postgres, auth (Clerk/NextAuth), Stripe billing, deployed on Vercel/GCP/AWS
- Data engineering: ETL pipelines, streaming (Kafka/Spark), warehouse modeling, dashboards
- Deployment: Docker, CI/CD, monitoring, Kubernetes when it's warranted

Recent work:

- ML Engineer at a Los Angeles startup: designed and deployed a vision-AI pipeline on GCP Vertex AI serving 5k+ inference requests a day at <200 ms p95 latency for 10+ B2B clients; a 50k-image labeling and augmentation workflow raised model accuracy by 12 percentage points
- Blog AI, an open-source content platform (56 GitHub stars): research → outline → per-section drafting → fact-check → SEO loop, Next.js + FastAPI, live in production with Clerk auth and Stripe billing
- TAlker, a RAG teaching assistant: hybrid BM25 + vector retrieval, cross-encoder reranking, RAGAS-style evaluation, six LLM providers behind one interface
- Genomics data pipelines at the DOE Joint Genome Institute that cut a 4-hour preprocessing step to 10 minutes

How I work: a short written plan before code, a working deployment you can
click on early, tests on the parts that matter, and plain-English updates.
Available for fixed-scope builds and ongoing development.

## 3) Rate — one number, used everywhere

**Set $75/hr** (live profile is still $50/hr — change it by hand; the
automated session was blocked from editing the rate field).

Why not $95: the account shows $700 lifetime earnings, three small fixed-price
jobs and no JSS. At $95 with that history the profile gets filtered out of
invites. Why not $50: it undercuts an M.S. plus production ML numbers and
attracts the wrong clients. Quote fixed-price work from the Project Catalog
tiers in §6, not hourly. Move to $95 after the next 2–3 reviews land.

## 4) Skills (Upwork allows 20 — live list as of 2026-08-31)

Python · SQL · Kubernetes · LangChain · Vector Database · FastAPI · OpenAI API
· Natural Language Processing · TypeScript · Next.js · React · Node.js ·
Docker · Large Language Model · Retrieval Augmented Generation · Chatbot
Development · PostgreSQL · Google Cloud Platform · ETL · Machine Learning

Kept the 14 that were already there (removed only "API Development") and
added the six AI/LLM-search terms. These are Upwork's exact labels.

## 5) Portfolio Items (verified 2026-08-31)

Each item: 1–3 screenshots, one concrete number, a link that loads. All links
below returned HTTP 200 on 2026-08-31. Ship the first five; add the rest
later. Private repos are marked — describe them, do not link to them.

1. **Blog AI — AI Content Generation Platform**
   Live: https://blog-ai.vivancedata.com · Code: https://github.com/gr8monk3ys/blog-AI (public, 56 stars)
   Generates long-form posts and books in a trained brand voice through a
   pipeline of small LLM calls: web research with up to 8 cited sources,
   outline, per-section drafting, proofreading, then an opt-in SEO rewrite
   loop and a claim-by-claim fact check. Providers (OpenAI, Anthropic,
   Gemini) sit behind one `generate_text()` with retries and per-operation
   rate limits. Next.js 16 + FastAPI, Clerk auth, Neon Postgres, Stripe
   billing; CI runs lint, type-check, unit, Playwright E2E, and a
   fresh-install migration smoke test on every push. Lighthouse 96
   accessibility, 100 SEO (2026-08-31).
   Screenshot source: `~/code/blog-AI/docs/screenshot.png`

2. **Link Flame — E-Commerce Platform**
   Live: https://link-flame-rouge.vercel.app · Code: https://github.com/gr8monk3ys/link-flame (public)
   Next.js storefront with product catalog, cart, and checkout: Prisma ORM on
   PostgreSQL, Stripe payments, NextAuth v5, Upstash Redis rate limiting,
   Tailwind UI, CI/CD to Vercel.
   Number: Lighthouse accessibility 96, best practices 93 (2026-08-31; see
   `lighthouse-2026-08-31.md`).

3. **TAlker — RAG Teaching Assistant**
   Code: https://github.com/gr8monk3ys/TAlker (public)
   Answers course questions from lecture notes. LangChain + ChromaDB with an
   `EnsembleRetriever` (BM25 + vector), optional cross-encoder reranking
   (`ms-marco-MiniLM-L-6-v2`), LLM query expansion, and a RAGAS-style
   LLM-as-judge evaluation page (faithfulness, answer relevancy, context
   precision/recall). Six providers (OpenAI, Anthropic, Gemini, Cohere,
   Ollama, HuggingFace) behind one factory; 62 mocked tests. Includes a
   Piazza bot that pulls course posts.
   Screenshot source: `~/code/TAlker/docs/assets/hero.png`

4. **InfiniStar — AI Character Chat App**
   Live: https://infini-star.vercel.app (code is private — do not link)
   Next.js 16 / React 19 app with streaming AI chat, real-time messaging via
   Pusher, creator profiles with follows, tips and subscriptions, Stripe
   checkout + billing portal + webhooks, Clerk auth, Prisma + Postgres,
   moderation reporting. Bun for dev and CI. Lighthouse 100 accessibility /
   100 best practices / 100 SEO (2026-08-31).
   Screenshot source: `~/code/InfiniStar/docs/screenshots/home.png`

5. **Production Vision-AI Pipeline (Sizzle, employment)**
   No link (employer work). Vertex AI + BigQuery pipeline serving 5k+ daily
   inference requests to mobile and web clients; fine-tuned vision model
   behind a Kotlin REST API at <200 ms p95 for 10+ B2B clients; labeling and
   augmentation workflow over 50k+ images, +12 pp model accuracy.
   Use an architecture diagram as the image, not a product screenshot.

6. **HuggingFace ML Portfolio**
   Code: https://github.com/gr8monk3ys/huggingface (public)
   14 published projects: a fine-tuned DistilBERT paper classifier (~95% F1),
   a resume-section classifier, Gradio Spaces for paper summarization, a
   model-comparison arena, and code explanation across 16 languages.

7. **Fraud Stream — Real-Time Fraud Detection Pipeline** (repo private —
   describe only)
   Kafka → Spark Structured Streaming → Snowflake medallion warehouse
   (Bronze/Silver/Gold), Avro schema registry, multi-level data-quality
   checks, HMAC-SHA256 PII masking, 8 fraud patterns detected at sub-second
   latency with configurable thresholds and alerting.

8. **Homelab — K3s GitOps Infrastructure** (repo private — describe only)
   Manifests for 43 self-hosted applications on K3s: MetalLB, Traefik +
   cert-manager, External Secrets Operator, SOPS/age-encrypted secrets, MinIO,
   Velero backups, kube-prometheus-stack, CrowdSec. Every change is validated
   in CI by yamllint, shellcheck, kubeconform, helm lint, and kustomize build.
   Say "CI-validated", not "production" — the README is explicit that the
   full stack hasn't been proven on a live cluster.

9. **Trading Bot — Algorithmic Trading Research**
   Code: https://github.com/gr8monk3ys/trading-bot (public)
   LSTM forecasting, FinBERT sentiment, DQN reinforcement learning, Alpaca
   WebSocket market data, backtesting across 6 strategies with 30+
   indicators, risk controls (circuit breakers, Kelly sizing, drawdown
   limits). The README says "no proven edge — not for real capital"; keep
   that framing. No profit claims.

10. **resume-AI — ATS Scoring and Resume Tailoring**
    Code: https://github.com/gr8monk3ys/resume-AI (public; runs locally, not deployed)
    FastAPI + Next.js. Five LLM providers behind one interface with an
    eight-class retryable error hierarchy and per-user response cache;
    deterministic algorithmic ATS scoring with LLM suggestions opt-in.

## 6) Project Catalog (create 2–3; fastest path to first contracts)

### A) Build a RAG Chatbot (Docs/Knowledge Base Assistant)
- Basic ($1,500 / 5 days): ingest docs + retrieval + prompt + evaluation checklist
- Standard ($3,500 / 10 days): Basic + simple UI + citations + deployment handoff
- Premium ($6,500 / 15 days): Standard + auth + analytics + production hardening

### B) Full-Stack MVP (Next.js + API)
- Basic ($1,200 / 5 days): landing + core pages + API skeleton + deployment
- Standard ($3,000 / 10 days): Basic + dashboard + DB + auth
- Premium ($6,000 / 15 days): Standard + payments/roles + CI/CD + monitoring basics

### C) Data Pipeline / ETL Build
- Basic ($1,200 / 5 days): requirements + first pipeline + docs
- Standard ($3,000 / 10 days): multiple pipelines + scheduling + QA checks
- Premium ($5,500 / 15 days): warehouse model + alerts + performance tuning

## 7) Employment History (matches the resume exactly)

### Machine Learning Engineer — Sizzle | Los Angeles, CA | Jun 2024 – May 2025
Designed and deployed an end-to-end vision-AI pipeline on GCP Vertex AI and
BigQuery serving 5k+ daily inference requests across mobile and web clients.
Integrated a fine-tuned vision model into a production Kotlin REST API at
<200 ms p95 latency for 10+ B2B clients. Built the labeling and
preprocessing workflow for a 50k+ image dataset; augmentation strategies
raised model accuracy by 12 percentage points.

### Freelance AI / Full-Stack Engineer — Self-employed (Upwork) | Aug 2022 – Present
Not added to Upwork's employment history — Upwork shows the contract
history itself (3 completed jobs, Feb–May 2026) and a freelance entry
claiming "since Aug 2022" would contradict it. If the resume keeps that
line, it needs off-platform client names behind it.

### Bioinformatics Data Analyst — DOE Joint Genome Institute | Berkeley, CA | May 2020 – Aug 2021
Data-processing pipelines in R for genomic homology comparison, cutting
processing time by 90%. High-throughput ETL for genome reference data, from 4
hours to 10 minutes. KNN model for plant–microbe interaction prediction (F1
0.68). Presented pipeline architecture to 1,000+ users and senior leadership.

Not listed: the G&M Trailer Repair operations role (non-technical; dilutes
the AI positioning) and Google SPS (student program).

## 8) Education & Certifications

- M.S. Applied Data Science — University of Southern California, Viterbi (Aug 2022 – Dec 2024)
- B.S. Computer Science & Engineering — University of California, Merced (Aug 2018 – May 2022)
- DeepLearning.AI Natural Language Processing Specialization (2025)
- Google Advanced Data Analytics Professional Certificate (2025)

## 9) Specialized Profiles (Upwork allows 2 — set both)

Specialized profiles get their own title/overview/skills and are shown to
clients searching that category. Set them up after the main profile.

**A) AI & Machine Learning**
Title: RAG & LLM Application Engineer | LangChain, OpenAI, FastAPI
Skills: Python, LangChain, RAG, LLM, OpenAI API, AI Chatbot, Vector Database, FastAPI, Machine Learning, Google Cloud Platform
Overview: §2 with the "Full-stack web apps" and "Data engineering" bullets cut and the TAlker/Blog AI paragraphs expanded.

**B) Web Development**
Title: Full-Stack Next.js Developer | TypeScript, FastAPI, Postgres, Stripe
Skills: Next.js, React, TypeScript, Node.js, FastAPI, PostgreSQL, Prisma, Stripe, Tailwind CSS, Vercel
Overview: §2 with the RAG bullet trimmed to one line and Link Flame / InfiniStar leading.

## 10) Availability & Settings

- Availability badge: ON, "More than 30 hrs/week" while ramping
- Profile visibility: Public
- Headshot: `https://lscaturchio.xyz/images/portrait.webp` is already public — reuse it
- Video intro: optional; skip for launch, don't block on it

## 11) Target jobs — the "I know I can land this" filter

Apply only when all of these hold. Every one of them is a stated fact above,
so the proposal can point at proof instead of promising.

| Signal | Threshold | Why |
|---|---|---|
| Posted | < 24 h | First 5 proposals get read; the 30th doesn't |
| Proposals | < 15 (Upwork shows "5 to 10" / "10 to 15") | Same |
| Client | payment verified, ≥ 1 hire or ≥ $1k spent | Unverified clients are where non-payment happens |
| Scope | one of the three catalog shapes (RAG bot, Next.js+API app, ETL) or a clear extension of one | Portfolio has a direct match |
| Budget | ≥ $1,000 fixed or ≥ $60/hr | Anything lower undercuts the $95 rate and the JSS risk isn't worth it |
| Stack | at least 3 of: Python, LangChain, OpenAI, FastAPI, Next.js, React, Postgres, GCP | Skills list matches on search |

Skip: "AI expert needed" with no scope, WordPress/Shopify plugins, anything
requiring on-site presence, anything with "test task first" unpaid.

Saved search terms (set in `settings.yaml`, run with `upwork jobs searches`
once the API is authorized):

- `RAG chatbot LangChain`
- `LLM integration FastAPI`
- `OpenAI API Python developer`
- `Next.js FastAPI full stack`
- `AI document Q&A`
- `ETL pipeline Python Postgres`

## 12) Proposal opener formula

The CLI drafts the body (`upwork propose generate --from-file job.md`). The
first two sentences are written by hand, every time, and follow this shape:

1. Restate their problem in one sentence using their own words.
2. Name the one portfolio item that is closest to it, with its number.

Then the CLI body, then a close that asks one scoping question. Never open
with "I am excited" or "I have read your job posting". See
`proposal-samples.md` for three worked examples.
