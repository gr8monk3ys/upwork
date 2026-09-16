# Upwork CLI

A terminal toolkit for one freelancer's Upwork workflow: finding jobs, judging
them, drafting proposals for them, and tracking what happened. Upwork's API is
read-mostly here — the terms below distinguish what this tool holds locally from
what Upwork owns.

## Language

**Job**:
A posting on the Upwork marketplace that a freelancer can apply to. Cached
locally so it can be judged and drafted against without an API call.
_Avoid_: listing, gig, posting, opportunity

**Score**:
A 1–10 judgement of how well one Job fits the freelancer's Profile. Absent
until it has been asked for, and absent again if the request failed — a Job
with no Score has never been successfully judged, never "scored zero".
_Avoid_: rating, rank, match score

**Score Result**:
A Job together with the outcome of one attempt to score it — a Score, or the
error that stopped it. What a scoring *run* returns, not what the cache
returns: the cache cannot say why an attempt failed, so it cannot produce one.
Successes are persisted, failures deliberately are not.
_Avoid_: scored job, job result, ranked job, job with score

A persisted Score still has no typed way back out of the cache on its own.
It reaches the Pipeline listing as `PipelineEntry.score`, and the reasoning
saved alongside it is never read at all. Closing that fully means a cache
read that returns the pairing; nothing needs it yet.

**Profile**:
The freelancer's own title, overview, skills, rate and portfolio. The thing a
Job is scored against and a Proposal is written from.
_Avoid_: resume, CV, bio, account

### Proposal and Application are not the same thing

These two collide badly, because Upwork's API calls its applications
`vendorProposals` while this tool stores something else under the word
"proposal". Keep them apart.

**Proposal**:
A cover letter drafted locally, by AI or by hand, for a Job. It lives only in
this tool: Upwork's terms of service forbid submitting one through the API, so
a Proposal is always copied out and submitted by hand. It has an Outcome once
the freelancer records one.
_Avoid_: cover letter (when referring to the stored record), bid, application

**Application**:
A proposal the freelancer has already submitted on Upwork, read back from
Upwork's API. Owned by Upwork, never created here.
_Avoid_: vendor proposal, submitted proposal, bid

**Offer**:
A contract Upwork's client has extended following an Application. Owned by
Upwork; this tool can read one and withdraw from it, nothing more.
_Avoid_: contract offer, invitation

### Tracking

**Pipeline**:
The local record of where each Job stands, moving through the Stages `found`,
`drafted`, `applied`, `interviewing`, `won` and `lost`.
_Avoid_: funnel, workflow, board

**Stage**:
One position in the Pipeline. A Job occupies exactly one at a time, and every
move between them is kept. The Stages that mean a Proposal actually went out
— `applied`, `interviewing`, `won`, `lost` — are what the win rate is measured
against, so a Job still at `found` or `drafted` does not count against it.
_Avoid_: status, state, step

**Outcome**:
What became of a Proposal — `won`, `lost` or `no_response`. Absent until the
freelancer records one: an unrecorded Outcome is not a loss. Recording `won`
or `lost` moves the Job to the matching Stage; `no_response` moves nothing,
because hearing nothing back is not yet a loss. The input to learning what a
winning Proposal looks like.
_Avoid_: result, disposition

### Searching

**Saved Search**:
A search term the freelancer keeps so it can be re-run without retyping.
Normalized and deduplicated: two terms differing only in whitespace are one.
_Avoid_: query, watch, alert term

**Cycle**:
One pass over one Saved Search — search, keep the Jobs not seen before, Score
them if scoring is available, and decide which are worth interrupting for. A
Cycle that finds nothing and a Cycle whose search failed are different
answers and never arrive as the same one.
_Avoid_: run, sweep, poll

**Contract**:
Work already won, read back from Upwork's engagements. Owned by Upwork; this
tool can read one and submit work against it, nothing more. Distinct from an
Offer, which precedes it.
_Avoid_: engagement, job (when it has been won)

**Milestone**:
One funded step of a fixed-price Contract. Only a Contract's own detail
payload can say what its Milestones are, so they are read with the Contract
and never inferred from a listing.
_Avoid_: phase, deliverable

**Bookmark**:
A Job the freelancer set aside by hand, with their note on why. Local, and
independent of the Pipeline: bookmarking a Job says "come back to this",
moving it through Stages says what became of it.
_Avoid_: favourite, star, saved job (which is a Saved Search term)

### Messaging

**Room**:
One Upwork conversation thread, owned by Upwork. Identified per company, not
globally, so a Room id is only meaningful alongside the company it belongs to.
_Avoid_: thread, channel, chat

**Message**:
One entry in a Room. Whether it is the freelancer's own cannot be answered by
the Message alone -- that needs a viewer, which is why a Conversation exists.
_Avoid_: story (Upwork's own word for it), post

**Conversation**:
A Room's Messages together with the id of whoever is reading them. The pairing
that can answer "is this mine?", which neither part can answer on its own.
_Avoid_: thread, history

### Money and movement

**Earning**:
One row of Upwork's finance report. Owned by Upwork and never written here.
The report names its own columns, which differ between accounts, so the
column labels travel with the rows rather than being assumed.
_Avoid_: payment, transaction, income

**Transition**:
One recorded move of a Job between Stages, kept forever. The first Transition
for a Job has no `from_stage`, because it came from nowhere.
_Avoid_: change, event, history entry
