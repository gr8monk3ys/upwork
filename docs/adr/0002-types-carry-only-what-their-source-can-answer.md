# A type carries only what its source can answer

A model does not get a field that some of its producers cannot fill honestly.
Where a fact depends on context the model does not have, the pairing gets its
own type instead.

Two examples in the code:

- `ScoreResult` pairs a `JobPosting` with the outcome of one scoring attempt,
  rather than putting `score` and `error` on `JobPosting`. A posting read from
  the marketplace has never been scored and never will be until someone asks;
  a nullable field there would be permanently half-empty and would invite
  callers to check it everywhere.
- `Conversation` carries a room's messages together with the id of whoever is
  reading them, rather than putting `is_own` on `Message`. A message read
  without a viewer has no honest answer to "is this mine?".

The rejected alternative in both cases is simpler and will look tempting: add
the field, default it, move on. It was considered and turned down because the
default is a lie for at least one producer, and because the flag has to be set
by whatever knows the missing context — which is exactly the module that can
return the pairing instead.

## Consequences

Slightly more types, and callers reach through one level (`result.job.title`,
`conversation.is_own(message)`). In exchange, no caller has to remember which
fields are meaningful on which instances, and no producer has to invent a
value it cannot know.
