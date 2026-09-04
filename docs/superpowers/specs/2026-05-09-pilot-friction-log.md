# Pilot Friction Log — 2026-05-09

**Spec:** docs/superpowers/specs/2026-05-09-pilot-design.md
**Plan:** docs/superpowers/plans/2026-05-09-pilot-execution.md
**Pilot started:** 19:38 PDT
**Pilot ended:** _(in progress)_

## Summary

| Severity | Count |
|---|---|
| blocker | 1 |
| annoyance | 1 |
| nit | 1 |

(Updated at end of pilot.)

## Entries

_(Entries appended below as the pilot proceeds.)_

### F-01: Keychain Anthropic key is dead but `config status` says "Set"
- **Step:** `upwork propose generate --from-file` (2026-08-31, manual loop)
- **Expected:** `config status` reporting "Anthropic API key: Set" means AI commands work.
- **Observed:** Every AI command fails with `Proposal generation failed: Invalid Anthropic API key. Check your key in settings.` A direct `GET /v1/models` with the keychain value returns `401 authentication_error`. The key was stored 2026-02 and has since been revoked/rotated.
- **Severity:** blocker (nothing AI-side works until the key is replaced)
- **Hypothesis:** `config status` only checks presence. A one-request liveness probe (`/v1/models`) in `config status` — or in `config setup` before saving — would have surfaced this six months earlier.

### F-02: `--from-file` always says "No client data available — skipping client research"
- **Step:** `propose generate --from-file job.md`
- **Expected:** The pasted posting usually contains client signals (payment verified, $ spent, hires, proposal count) — the drafts would be better for using them.
- **Observed:** Research is skipped unconditionally on the file path; the posting's trailing "Payment verified · $12k spent · 4 hires" line is ignored.
- **Severity:** annoyance
- **Hypothesis:** Parse the common Upwork footer patterns from the file text into the same client dict the API path builds.

### F-03: Boxed output is hard to copy
- **Step:** Reading the generated proposal to paste into Upwork
- **Expected:** Plain text ready for the clipboard.
- **Observed:** Both `generate` and `propose show N` print a Rich panel wrapped at terminal width with `│` borders; there is no `--plain`/`--raw` flag, and no clipboard copy was observed after `generate` (the clipboard still held its previous contents).
- **Severity:** nit
