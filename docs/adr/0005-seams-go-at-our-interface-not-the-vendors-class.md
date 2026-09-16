# A seam goes at our interface, not the vendor's class

Where an external service is involved, the substitution point is a function
this codebase owns — `client.get_client`, `ai/utils.get_completer` — and the
fake satisfies *that*, in `tests/fakes.py`. Tests never patch a vendor class
name.

The AI layer had it the other way round for a while, and the cost was
legible. `complete` constructed `Anthropic` inside itself, so there was no
injection point at all, and 46 test sites across seven modules patched
`upwork_cli.ai.utils.Anthropic`, hand-built `MagicMock` response objects with
the right `.content[].type` shape, and constructed
`anthropic.AuthenticationError(response=MagicMock(status_code=401), body=...)`
to exercise one `except` branch. Seven test modules knew the SDK's exception
constructors. The Upwork side, which had `get_client` and `FakeUpworkClient`,
needed none of that.

`AnthropicCompleter` is the real adapter and the only place the SDK appears;
`FakeCompleter` is the second. Two adapters, one seam.

## Consequences

An SDK upgrade touches one class. A test that wants to assert what reached the
model reads `FakeCompleter.prompt` instead of digging through
`call_args.kwargs["messages"][0]["content"]`, which is cheap enough that
several tests now check it and did not before.

The vendor's exception types still appear in exactly one test class —
`TestAnthropicCompleter` — because translating them is what that class is
for. That is the boundary of the rule, not an exception to it.

The rule has a cost when a fake drifts from the real adapter: `FakeUpworkClient`
was missing `get_engagements`, `get_engagement` and `submit_work`, and rather
than notice, the contracts tests quietly fell back to `MagicMock`. A fake that
does not cover the whole seam is worse than no fake, because the gap is
invisible. Extend the fake when you extend the seam.
