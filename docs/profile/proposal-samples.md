# Proposal Samples (CLI output, 2026-08-31)

Three representative jobs — one per Project Catalog shape — drafted with
`upwork propose generate --from-file <job.md> --tone professional --length medium`
against the profile in `profile.yaml`. The jobs are realistic composites, not
real postings. The drafts are verbatim CLI output; nothing was hand-edited, so
this is the floor, not the ceiling — §12 of the packet says the first two
sentences get rewritten by hand for the real posting.

Every claim in the drafts traces to a fact in the packet. Check that stays true
after any profile change: the model only knows what `profile.yaml` tells it.

## A — RAG chatbot ($4,000 fixed)

### Job posting

```text
Title: Build a RAG chatbot over our internal documentation (Python, LangChain, OpenAI)

We're a 40-person B2B SaaS company with ~1,200 pages of internal docs (Confluence exports as HTML/Markdown, plus PDFs) and support macros. We want an internal assistant our support and sales teams can ask questions like "what's our SLA for enterprise customers" and get an answer with a link to the source page.

Requirements:
- Ingest Markdown/HTML/PDF, keep it updated when docs change (weekly re-index is fine)
- Retrieval that actually cites the source page; hallucinated answers are a dealbreaker for us
- OpenAI models are fine; we already have an API key. Open to Anthropic.
- Simple web UI (we don't care about pretty) with Google SSO
- Deployed to our GCP project, or Docker image we can run on Cloud Run
- Some way for us to test answer quality — we've been burned by a previous contractor whose bot "worked in the demo"

Budget: $4,000 fixed. Timeline: 3 weeks. Please tell us about a similar system you've built and how you evaluated it.
Posted 3 hours ago · Proposals: 5 to 10 · Payment verified · $12k spent · 4 hires
```

### CLI draft

"Worked in the demo" is exactly what an evaluation harness prevents — and
it's the part most RAG builds skip. On TAlker, a RAG teaching assistant I
built, I wired in RAGAS-style scoring (faithfulness, answer relevancy,
context precision/recall) so retrieval quality was a number I could watch,
not a vibe. You'd get the same thing here: a golden set of ~50 real
questions from your support and sales teams, scored on every re-index, with
a report you can read yourself. If faithfulness drops after a doc change,
you'll know before your team does.

On the hallucination dealbreaker: TAlker used hybrid BM25 + vector retrieval
with cross-encoder reranking, and answers were constrained to retrieved
context with citations attached at the chunk level — no source, no answer.
Confluence HTML/Markdown and PDF ingestion is straightforward; the weekly
re-index runs as a scheduled Cloud Run job with content hashing so unchanged
pages aren't re-embedded.

Deployment is familiar ground — I ran a Vertex AI pipeline on GCP serving
5k+ requests/day at Sizzle. You'd get a Docker image for Cloud Run, thin
FastAPI + minimal UI, Google SSO via your Workspace.

$4,000 and 3 weeks is workable. Can we do a 20-minute call so I can see a
sample of your docs and confirm chunking strategy before I write the plan?

## B — Next.js + FastAPI MVP ($6,000 fixed)

### Job posting

```text
Title: Full-stack developer to build MVP: Next.js + FastAPI + Stripe subscriptions

I'm a solo founder with a validated idea (150 people on a waitlist). I need an MVP built:
- Next.js frontend with auth (Clerk or similar), a dashboard, and 3–4 core pages
- Python FastAPI backend calling the OpenAI API to generate personalized reports from a form the user fills in
- Postgres database, Stripe subscriptions (monthly/annual), webhook handling
- Deployed on Vercel + something for the backend, with CI so I'm not manually deploying

I have Figma designs done. Looking for someone who has shipped this exact stack before and can show me a live app they built, not just a GitHub repo. Fixed price, $6,000, 4 weeks. Would like to keep working together after launch if it goes well.
Posted 6 hours ago · Proposals: less than 5 · Payment verified · $3.5k spent · 2 hires
```

### CLI draft

You asked for someone who's shipped this exact stack with a live app to
click on — I have two.

Blog AI is Next.js + FastAPI + Clerk + Neon Postgres + Stripe, live, with an
OpenAI-backed multi-stage generation pipeline (research → outline → drafting
→ fact-check) that's structurally very close to your "form in, personalized
report out" flow. InfiniStar is a live Next.js app with Stripe checkout, the
billing portal, and webhook handling for monthly subscriptions — I'll send
you both URLs so you can create an account and hit checkout yourself.

The part founders usually underestimate here is webhook reliability and
generation latency. Subscription state has to survive failed/retried
webhooks, and OpenAI report generation on a form submit will time out on a
plain request/response setup — I'd run it as a background job with status
polling so the dashboard shows progress instead of a spinner that dies.
Backend goes on Render or Fly.io in Docker; frontend on Vercel; GitHub
Actions running lint, type-check, tests, and migrations on every push, so no
manual deploys.

$6,000 over 4 weeks works. I'd start with a one-page written plan and a
clickable deployed shell in week one, then build outward from your Figma.

Can we do a 20-minute call this week to walk through the report logic?

## C — ETL pipeline ($60–90/hr)

### Job posting

```text
Title: Python data engineer — ETL pipeline from 6 SaaS APIs into Postgres + dashboard

Ecommerce agency. We pull data from Shopify, Klaviyo, Meta Ads, Google Ads, GA4 and a shipping provider by hand into spreadsheets every Monday. Want this automated: nightly pulls into a Postgres warehouse with a clean reporting schema, data quality checks so we know when a source breaks, and a Metabase (or similar) dashboard on top.

Must-haves: Python, Postgres, scheduling (Airflow/Prefect/cron — your call, justify it), Docker so it runs on our small VPS. Nice: experience with the marketing APIs listed.
Hourly, $60–90/hr, est. 60–80 hours to start, ongoing maintenance after.
Posted 1 hour ago · Proposals: 5 to 10 · Payment verified · $28k spent · 11 hires
```

### CLI draft

Six hand-pulled sources every Monday means your reporting is always a week
stale and one API change away from silently wrong numbers. The fix isn't
just scheduling scripts — it's a warehouse layer where each source lands
raw, gets modeled into a clean reporting schema, and fails loudly when Meta
rotates a token or GA4 changes a field name.

I'd use Prefect over Airflow here. On a small VPS, Airflow's scheduler,
webserver, and metadata DB will eat your resources; Prefect runs as a single
lightweight worker in Docker Compose alongside Postgres and Metabase, and
its retry/alerting model fits API pulls better than cron with no
observability.

Closest relevant work: I built a streaming fraud pipeline with a
Bronze/Silver/Gold warehouse, schema registry, and multi-level data quality
checks with configurable alerting — the same
freshness/row-count/null-rate/schema-drift patterns your marketing sources
need. Earlier, I rebuilt a genomics ETL at the DOE Joint Genome Institute
from 4 hours to 10 minutes. Postgres, Docker, and Python are daily tools for
me.

Suggested first step: land Shopify and Klaviyo end-to-end in week one — raw
tables, reporting views, and one Metabase dashboard — so you can kill one
spreadsheet before we scale to the remaining four.

Open to a 20-minute call to review your current spreadsheet columns?

## What to change by hand before sending

- RAG draft: replace "~50 real questions" with a number after seeing their docs; keep the "no source, no answer" line — it answers their stated dealbreaker.
- MVP draft: paste the two live URLs (blog-ai.vivancedata.com, infini-star.vercel.app) into the Upwork message once the client has replied — links in the first proposal get filtered.
- ETL draft: the Prefect-over-Airflow justification is the differentiator; if the client already runs Airflow, flip it rather than argue.
- All three: the closing question is the ask. Don't add a second one.
