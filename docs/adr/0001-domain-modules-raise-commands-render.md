# Domain modules raise; commands render and choose the exit code

Every module between the commands and an external service — `messaging`,
`earnings`, `applications`, `jobs`, `scoring`, `ai/utils` — reports failure by
raising a typed error (`MessagingError`, `EarningsError`, and so on, all
`RuntimeError` subclasses). None of them print, and none of them exit. The
command that called them decides what the user sees and what the process
returns, via `output.fail`.

This was not the original shape: the logic these modules now hold used to sit
inside command bodies, where printing and exiting at the point of failure was
the obvious thing to do. Extracting it made that impossible to keep — a module
that prints cannot be tested without capturing stdout, and cannot be reused by
a caller that wants to carry on. `propose generate` relies on exactly that: it
catches the researcher's error and drafts without client research rather than
aborting.

## Consequences

`ai/scorer.py` is the one deliberate exception. It drives a Rich progress bar
during a batch of concurrent calls, which is presentation living in the AI
layer. Moving it means designing a progress-reporting seam, which has not been
done; until it is, that module keeps its own `Console`.
