# Dogfood Pilot Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (NOT subagent-driven-development — this plan requires the user driving the terminal). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Walk one full morning-routine flow of `upwork-cli` against real Upwork data and a real Anthropic key, capturing every friction point in a structured log so the next design round can prioritize fixes from evidence.

**Architecture:** Two-actor execution. The repo owner runs each command in their own terminal. Claude tails the friction log and writes entries as observations come in. No code is changed during the pilot.

**Tech Stack:** `upwork-cli` (already installed locally via `uv sync --extra test` or `pip install -e .`), Anthropic API, real Upwork API app, plain Markdown for the friction log.

---

## Spec reference

Driven by `docs/superpowers/specs/2026-05-09-pilot-design.md`. Decision criteria, severity rubric, scope, and roles all come from there. This plan implements that spec as a sequence of executable steps.

## Plan-wide rules (apply to every task)

- **The user runs every command** in their own terminal. Claude does not run `upwork ...` commands during the pilot.
- **Claude does not edit `upwork-cli` source** during the pilot. Only the friction log file gets written.
- **After every task**, Claude asks the user "any friction to log here?" before moving on. Even nits go in.
- **On a `blocker`-severity friction**, stop the pilot. Do not push through. The remaining tasks become "skipped — see F-NN."
- **Friction log entries are numbered F-01, F-02, …** in the order they happen. No renumbering.
- **AI output quality is friction**, even if no error occurred. "The proposal sounds generic" is `annoyance` severity.

## Files

- Create: `docs/superpowers/specs/2026-05-09-pilot-friction-log.md` — the friction log; one entry per observation.
- No source files modified.

---

### Task 1: Create the friction log scaffold

**Files:**
- Create: `docs/superpowers/specs/2026-05-09-pilot-friction-log.md`

- [ ] **Step 1: Write the friction log header**

Claude writes this file before the user runs any command:

```markdown
# Pilot Friction Log — 2026-05-09

**Spec:** docs/superpowers/specs/2026-05-09-pilot-design.md
**Plan:** docs/superpowers/plans/2026-05-09-pilot-execution.md
**Pilot started:** <fill in when pilot starts, e.g. 14:32 PT>
**Pilot ended:** <fill in at end>

## Summary

| Severity | Count |
|---|---|
| blocker | 0 |
| annoyance | 0 |
| nit | 0 |

(Update at end of pilot.)

## Entries

(Entries appended below as the pilot proceeds.)
```

- [ ] **Step 2: Commit the empty log**

```bash
git add docs/superpowers/specs/2026-05-09-pilot-friction-log.md
git commit -m "docs: scaffold pilot friction log"
```

---

### Task 2: Verify pre-flight environment

**Files:** None modified. Diagnostic only.

This task confirms the environment matches the spec's pre-flight assumptions before any pilot work begins. If something is off, this is also a friction signal worth logging.

- [ ] **Step 1: User confirms `upwork` command is on PATH**

Run: `which upwork && upwork --help | head -20`
Expected: prints a path and a Click help banner with command groups (config, jobs, propose, applications, offers, earnings, contracts, messages, pipeline).

If `upwork` is not found:
- Suspected cause: package not installed in the active environment.
- Recovery: `uv sync --extra test` then `source .venv/bin/activate`, or `pip install -e ".[test]"`.
- This counts as F-01 if it surprises the user (i.e., they thought it was installed).

- [ ] **Step 2: User confirms `~/.config/upwork-cli/` is empty or sane**

Run: `ls -la ~/.config/upwork-cli/ 2>/dev/null || echo "no config dir yet"`
Expected: either "no config dir yet" (clean install) or a directory with `settings.yaml` / `auth.json` from prior runs.

If a stale partial setup exists, decide: keep it for this pilot (treat any oddness as friction), or wipe with `rm -rf ~/.config/upwork-cli/` for a clean run.

- [ ] **Step 3: User confirms env vars are NOT set**

Run: `env | grep -E "^(UPWORK_CLIENT_SECRET|ANTHROPIC_API_KEY|DISCORD_WEBHOOK_URL)="`
Expected: no output, OR output but the user is aware of it.

The pilot exercises the keyring path. If env vars are set, they override keyring. Either:
- Unset them for this session: `unset UPWORK_CLIENT_SECRET ANTHROPIC_API_KEY DISCORD_WEBHOOK_URL`, or
- Decide to test the env-var path explicitly (note this in the friction log as a deliberate test choice, not a friction).

- [ ] **Step 4: Claude pauses for friction-log entries**

Claude asks the user: "Anything weird in pre-flight worth logging?"
Append any entries to the friction log. Format:

```markdown
### F-NN: <short title>
- **Step:** Pre-flight
- **Expected:** <what we thought>
- **Observed:** <what happened>
- **Severity:** blocker | annoyance | nit
- **Quote/screenshot:** <if applicable>
- **Hypothesis:** <if obvious>
```

- [ ] **Step 5: Decision rule**

If any pre-flight friction was severity `blocker`, stop the pilot here. The blocker becomes the entire finding. Otherwise, proceed.

---

### Task 3: Run `upwork config setup`

**Files:** None modified.

This is the OAuth + secrets setup wizard. It's the highest-suspicion step — the on-ramp ends or begins here.

- [ ] **Step 1: User runs setup**

Run: `upwork config setup`
Expected: an interactive prompt asking for Client ID, redirect URI, Client Secret, Anthropic API key (in that order or close to it). Then opens a browser for OAuth. Then captures and stores tokens in `auth.json`.

- [ ] **Step 2: User narrates each prompt**

For each prompt:
- Did the prompt text make sense?
- Did the default value make sense?
- Did the secret-entry behavior (no echo) feel safe?
- Was it clear what to type?

Claude logs any "huh" moments as nits.

- [ ] **Step 3: User completes OAuth callback**

Browser opens → user authorizes → callback returns. The terminal should report success.
Expected: a "configured" or "tokens saved" confirmation message.

If the callback hangs, errors, or asks the user to do something that wasn't obvious from the CLI prompts, log severity `blocker` (auth is the spine of everything else).

- [ ] **Step 4: User runs status check**

Run: `upwork config status`
Expected: shows configured fields, secret presence (without revealing values), and a "ready" indicator.

If status reports inconsistencies (e.g., "client_id set but no token"), that's an `annoyance` at minimum — the user has to mentally reconcile.

- [ ] **Step 5: Claude pauses for friction-log entries**

Append any entries from this task. If multiple prompts felt off, each gets its own entry — don't bundle.

- [ ] **Step 6: Decision rule**

If a `blocker` was logged, stop. Otherwise proceed.

---

### Task 4: Import the freelancer profile

**Files:** None modified.

The repo already contains `upwork-profile-draft` (228 lines of personal positioning content). The AI uses this profile for scoring and proposal generation, so import quality directly affects all downstream output.

- [ ] **Step 1: User imports the profile**

Run: `upwork config profile --file upwork-profile-draft`
Expected: a confirmation that the profile was parsed, with key fields shown (title, overview length, skills count, rate). The CLI should report what it extracted.

- [ ] **Step 2: User reads the parsed summary**

Compare to the source file. Did the parser pick up:
- The title line ("AI & Full-Stack Developer | Python, TypeScript, Next.js | RAG Systems, LLMs & Data Pipelines")?
- The skills list?
- Rate range ($75-$125/hr)?
- Portfolio entries (if any)?

If the parser silently dropped things, log `annoyance` severity at minimum. Quote the missing field in the entry.

- [ ] **Step 3: User runs profile audit**

Run: `upwork config audit`
Expected: AI returns a profile audit report — coverage score (0-100) and suggested improvements.

If the audit hangs, fails, or returns an obviously generic response that ignores the profile content, log it. Audit quality is a proxy for downstream AI quality.

- [ ] **Step 4: Claude pauses for friction-log entries**

- [ ] **Step 5: Decision rule**

If profile import failed entirely (`blocker`), stop — search and propose can't run. Otherwise proceed.

---

### Task 5: Run a real job search

**Files:** None modified.

This step exercises Upwork's GraphQL via the OAuth token from Task 3.

- [ ] **Step 1: User picks one keyword from `upwork-profile-packet`**

Suggested candidates (the user picks one):
- "RAG developer"
- "LLM engineer"
- "Next.js full-stack"
- "data pipeline engineer"
- "Python backend developer"

Claude writes the chosen keyword into the friction log as context.

- [ ] **Step 2: User runs search**

Run: `upwork jobs search "<chosen keyword>" --limit 10`
Expected: a Rich-formatted table with up to 10 jobs (title, budget, skills, client country, posted). The DB caches results.

If the table is empty, the formatting wraps badly, columns are confusing, or budget rendering is wrong, log it.

- [ ] **Step 3: User adds budget/recency filters**

Run: `upwork jobs search "<chosen keyword>" --budget-min 1000 --posted 24h --limit 10`
Expected: a smaller filtered table, still well-formatted.

If the filters silently return nothing without explaining "no results match" vs. "API error," log `annoyance`.

- [ ] **Step 4: Claude pauses for friction-log entries**

- [ ] **Step 5: Decision rule**

If search returned 0 jobs across all filters, the pilot stops being useful. Try a broader keyword. If still 0, log `blocker` and stop — there's nothing to score.

---

### Task 6: Score jobs against the profile

**Files:** None modified.

This is where AI quality first becomes visible.

- [ ] **Step 1: User runs scoring**

Run: `upwork jobs score`
Expected: a progress spinner, then per-job scores 1-10 cached to the DB. Final summary table sorted by score.

If scoring takes longer than ~30s/job, log `annoyance` (cost/latency proxy).
If multiple jobs come back with score=0, that's the AI's silent-fallback path firing — log `blocker` because the score field is now meaningless.

- [ ] **Step 2: User runs `jobs saved` or re-runs `search` to view scores**

Run: `upwork jobs search "<chosen keyword>" --limit 10`
Or whatever surfaces the scored jobs. Expected: scores visible in the table or a separate scored view.

- [ ] **Step 3: User picks the top-scored job and reads its score reasoning**

Run: `upwork jobs detail <id>` for the top-scored job.
Expected: full job description plus the AI score *and* the reasoning behind it.

The user reads the reasoning critically:
- Does it cite specific skill matches from the profile?
- Does it mention budget appropriateness for the user's $75-$125/hr range?
- Or does it sound like generic LLM filler?

If the reasoning is generic, log severity `annoyance` — quality matters because the user's adoption depends on trust.

- [ ] **Step 4: Claude pauses for friction-log entries**

- [ ] **Step 5: Decision rule**

If scoring failed entirely (no scores written), `blocker`, stop. Otherwise proceed.

---

### Task 7: Generate a proposal for the top job

**Files:** None modified.

This is the headline AI feature — output quality determines whether the tool earns the user's daily attention.

- [ ] **Step 1: User generates a proposal**

Run: `upwork propose generate <top-job-id>`
Expected: a Rich-rendered proposal cover letter, with default tone (professional) and length (medium, ~200 words).

- [ ] **Step 2: User reads the proposal as if they were going to send it**

Critical questions:
- Does it open with something specific to *this* job, or a generic hook?
- Does it cite a credential from the user's profile that's relevant?
- Does it close with a concrete next-step ask?
- Does it sound like the user's voice, or like ChatGPT?

If "no" to two or more of these, log `annoyance`. If "no" to all, log `blocker` — the headline feature isn't useful enough to use.

Quote the worst sentence in the friction-log entry.

- [ ] **Step 3: User checks proposal storage**

Run: `upwork propose history`
Expected: lists the proposal we just generated. Confirms persistence works.

- [ ] **Step 4: Claude pauses for friction-log entries**

- [ ] **Step 5: Decision rule**

If proposal generation failed entirely, `blocker`, stop. If it produced output, proceed regardless of quality (quality is logged, not a blocker).

---

### Task 8 (optional): Refine the proposal once

**Files:** None modified.

Skip this task if any earlier task hit time pressure. The pilot is whole without it; refinement is a depth probe.

- [ ] **Step 1: User runs one refinement**

Run: `upwork propose refine --feedback "make this more specific to the project's tech stack and shorter"`
Expected: a new version of the proposal that adapts. The history grows by one.

- [ ] **Step 2: User compares the two versions**

Did the refinement actually do what was asked? Did the second version sound *less* like the user's voice (sometimes refinements wash out personality)?

If the refinement ignored the feedback or made things worse, log `annoyance`.

- [ ] **Step 3: Claude pauses for friction-log entries**

- [ ] **Step 4: Decision rule**

Always proceed — refinement is optional, not blocking.

---

### Task 9 (optional): Save to pipeline

**Files:** None modified.

Skip if running long. Verifies the pipeline wiring works.

- [ ] **Step 1: User moves the job into the pipeline**

Run: `upwork pipeline move <top-job-id> applied --notes "pilot test"`
Expected: confirmation. State persisted in the DB.

- [ ] **Step 2: User views the pipeline**

Run: `upwork pipeline view`
Expected: the job appears under "applied".

If the move silently fails, or the view doesn't reflect it, log `annoyance` (pipeline UX rough edges were already flagged in the architecture review — confirm or refute).

- [ ] **Step 3: Claude pauses for friction-log entries**

---

### Task 10: Triage the friction log and apply the decision rule

**Files:**
- Modify: `docs/superpowers/specs/2026-05-09-pilot-friction-log.md` (fill in summary, end timestamp).

- [ ] **Step 1: Fill the summary table**

Count entries by severity. Update the table at the top of the friction log:

```markdown
## Summary

| Severity | Count |
|---|---|
| blocker | <count> |
| annoyance | <count> |
| nit | <count> |
```

- [ ] **Step 2: Apply the decision rule from the spec**

From `docs/superpowers/specs/2026-05-09-pilot-design.md`:

| Result | Next step |
|---|---|
| 0–2 friction points, no blockers | Ship as-is. Pivot to other work. |
| 3–5 friction points OR any blocker | Design fixes for them in a follow-up brainstorming. |
| 6+ friction points OR multiple blockers | Density signals a redesign of the on-ramp or daily flow rather than point fixes. |

Append a "## Decision" section to the friction log explaining which bucket we're in and what happens next.

- [ ] **Step 3: Commit the friction log**

```bash
git add docs/superpowers/specs/2026-05-09-pilot-friction-log.md
git commit -m "docs: capture pilot friction log and decision"
```

- [ ] **Step 4: Suggest the next conversation starter**

Based on the bucket:
- "Ship as-is" → end of brainstorming session; user picks next thread.
- "Fix N items" → start a new brainstorming session with the friction log as input.
- "Redesign on-ramp/flow" → start a new brainstorming session referencing options B or C from the original brainstorming.

Claude writes a one-paragraph summary of the recommended next step into the same commit (or as a follow-up commit).

---

## Self-review

**Spec coverage:** Every requirement in `2026-05-09-pilot-design.md` has at least one task:
- Goal & success criteria → Task 10 (triage produces the ranked log)
- Pre-flight conditions → Task 2
- Pilot scenario steps 1–8 → Tasks 3–9 (one task per spec step, in order)
- Capture protocol → Tasks 1, 3-9 (every task has a "pause for entries" step)
- Decision criteria → Task 10
- Roles → Plan-wide rules
- Out-of-scope → respected (no edge-case commands appear in any task)

**Placeholder scan:** No "TBD" / "implement later" / "similar to Task N" patterns. The friction-log entry shape is defined in Task 1's commit and used identically in all later tasks.

**Type/name consistency:** Friction-log entry fields (`Step`, `Expected`, `Observed`, `Severity`, `Quote/screenshot`, `Hypothesis`) and severity tags (`blocker`, `annoyance`, `nit`) are identical across the spec, the plan, and every task that references them.
