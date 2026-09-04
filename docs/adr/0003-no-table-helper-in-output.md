# `output` has no table helper

`upwork_cli/output.py` holds the shared console, `fail`, `empty`, `warn`,
`money` and `truncate` — everything the seven command modules were deciding
separately, and which all seven now use: no command module raises `SystemExit`
by hand any more. It deliberately does **not** wrap `rich.Table`, even though the CLI
builds seventeen tables inline and consolidating them looks like the obvious
next step.

It was tried and rejected. The tables differ in column styles, widths,
`no_wrap`, `justify`, `max_width` and per-cell markup; a helper general enough
to build all seventeen would take roughly as many arguments as `rich.Table`
itself and hide nothing. That is a shallow module — an interface as complex as
its implementation — which is the thing this codebase spent a refactor
removing, so adding one here would have been a step backwards.

The duplication worth removing was the *decisions* every command was making
independently: what a failure does to the exit code, what "nothing found"
looks like, and how money reads. Those are in `output`. Table construction is
not duplication; it is seventeen genuinely different tables.
