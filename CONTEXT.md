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

A persisted Score currently has no typed way back out of the cache. It is
written by a scoring run and read again only as an untyped column inside
`pipeline view`; the reasoning saved alongside it is never read at all. Any
work on the Pipeline should close that gap rather than route around it.

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
move between them is kept.
_Avoid_: status, state, step

**Outcome**:
What became of a Proposal — `won`, `lost` or `no_response`. Recorded by hand,
and the input to learning what a winning Proposal looks like.
_Avoid_: result, disposition
