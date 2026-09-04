# Failure exits 1; nothing found exits 0

`output.fail` always exits 1 and `output.empty` always exits 0, and the
distinction the exit code carries is *failure* versus *nothing to do* — not
*error* versus *warning*, and not *severe* versus *mild*.

Three commands used to disagree. `jobs detail <unknown>`, `jobs score` with an
empty Profile, and `jobs watch --notify discord` without a webhook all
reported a problem and exited 0, while `applications` exited 1 for the
identical condition — and `searches run` exited 1 for the same webhook guard
that `jobs watch` exited 0 for, three lines away. Two of the three were pinned
by tests named `..._reports_and_exits_zero`, so the inconsistency was
deliberate at some point and had simply never been decided.

They exit 1 now. The tests were rewritten rather than deleted, so the change
of policy is visible in the diff rather than looking like a bug fix.

## Consequences

A script can branch on the exit code. `upwork jobs detail X || handle_missing`
means what it says, and a cron job that pipes `jobs searches run` will notice a
failed search rather than treating it as a quiet night.

The cost is that "not found" is now a failure, which is a defensible thing to
disagree with: an empty search result and a job that does not exist are not
obviously the same kind of nothing. The rule that settles it here is whether
the *command could do its job*. `pipeline view` with no jobs did its job and
found nothing — exit 0. `jobs detail X` was asked for one specific thing and
could not produce it — exit 1.

A module raising is not by itself a failure; see ADR-0001 on
`watchlist.AlreadySaved`.
