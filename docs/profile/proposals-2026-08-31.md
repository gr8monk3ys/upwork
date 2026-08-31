# Proposals prepared 2026-08-31 (real postings)

Both drafted with `upwork propose generate --from-file`, then the opening
rewritten by hand (packet §12). Left in Upwork's Apply form for the user to
review and click Send — never submitted by automation.

## A — Senior AI & Machine Learning Product Lead — FinTech AI agents
- Job: https://www.upwork.com/jobs/~022094068704654156900
- Posted 2026-08-30 · $65–$128/hr · <30 hrs/wk · 1–3 months · US-only · 26 Connects
- Client: 5.0 (8 reviews), $5.1K spent, 12 hires, $53.66/hr avg paid, Pullman WA
- Risk: 50+ proposals (boost auction 1st place = 550 Connects; don't)
- Bid entered: $85/hr (mid-range; client's avg paid is $54, top freelancers on this client were $80)
- CLI proposal id: #7 (`upwork pipeline move manual-8d46724f applied` after sending)

Cover letter (as pasted):

> A fraud or risk call an agent makes has to survive an audit, and LLM reasoning alone doesn't — which is why your line about combining deterministic rules with ML predictions is the right architecture, not a compromise. In practice: rules and model scores produce the verdict; the agent does investigation, evidence gathering and explanation, with structured outputs you can log and replay.
>
> Three pieces of my background map directly onto this:
>
> • Fraud Stream — a real-time detection pipeline I built on Kafka → Spark Structured Streaming → Snowflake (Bronze/Silver/Gold) with an Avro schema registry, multi-level data-quality checks, HMAC-SHA256 PII masking, and 8 fraud patterns firing at sub-second latency.
>
> • TAlker — a LangChain RAG system with hybrid BM25 + vector retrieval, cross-encoder reranking, and RAGAS-style evaluation on faithfulness and context precision. Evaluation strategy is where most agent products fail; I treat the eval harness as a first-class deliverable.
>
> • Sizzle (ML Engineer, 2024–25) — a production Vertex AI pipeline serving 5k+ inferences a day at under 200 ms p95 for 10+ B2B clients, plus the labeling and augmentation work that raised model accuracy by 12 points.
>
> Stack overlap with yours: Python, LangChain/LangGraph, FastAPI, PostgreSQL, Docker, scikit-learn/XGBoost, AWS and GCP. M.S. in Applied Data Science (USC). Based in Santa Monica, so US hours are my hours.
>
> I'd start with a written architecture brief — agent boundaries, the rules/ML/LLM decision split, human-in-the-loop points, and an eval harness spec — before any orchestration code.
>
> Open to a 20-minute call this week to walk through your current data sources and risk signals?

## B — Senior AI Engineer to Build an AI Sales Operations Employee
- Job: https://www.upwork.com/jobs/~022082059740997677549
- Posted ~2026-07 · $30–$45/hr · 30+ hrs/wk · 3–6 months · contract-to-hire · 26 Connects
- Client: 4.9 (1 review), $1.5K spent, 1 hire, Chicago. **Last viewed 4 weeks ago** — may be dead.
- Must start with "Not another SDR" and answer 3 questions; 4 screening questions in the form.
- CLI proposal id: #8 (`upwork pipeline move manual-47bed4ae applied` after sending)

Cover letter (final):

> Not another SDR.
>
> The hard part of an autonomous sales employee isn't calling an LLM — it's making the agent's decisions auditable and recoverable. A run that researches a prospect, scores it against your ICP, writes outreach, and then writes back to the CRM needs durable state, retries on partial failure, and guardrails so it never emails the wrong contact twice.
>
> 1. Architecture: a supervisor agent (LangGraph) that plans a per-lead workflow and dispatches to specialist tools — research (web + enrichment APIs), scoring (ICP rules + an LLM rubric with a confidence score), outreach generation, CRM write-back, calendar booking — each step persisted in Postgres so a run can pause, resume, or be reviewed. Deterministic rules decide "should we engage at all"; the LLM writes and explains. Human-in-the-loop on anything irreversible until the eval numbers earn autonomy.
>
> 2. Most relevant production project: Blog AI, live at blog-ai.vivancedata.com — a multi-stage pipeline (research with cited sources → outline → drafting → fact-check → SEO loop) behind one provider abstraction over OpenAI/Anthropic/Gemini with retries and per-operation rate limits, Next.js + FastAPI, Clerk auth, Stripe billing, Playwright E2E in CI. Same shape as your pipeline, different domain.
>
> 3. In production: LangChain (TAlker — hybrid BM25 + vector RAG with cross-encoder reranking and RAGAS-style evaluation), OpenAI, Anthropic and Gemini APIs, FastAPI, Postgres/pgvector, Docker, GitHub Actions; Vertex AI at Sizzle serving 5k+ inferences a day at under 200 ms p95.
>
> I'd start with a one-page architecture plan and a clickable skeleton in week one, then build outward tool by tool with an eval harness measuring lead-score accuracy and outreach quality.
>
> Open to a 30-minute call to pressure-test scope and sequencing?
