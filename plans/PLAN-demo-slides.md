# Demo slides

Status: **working deck created, scientific demo replacement pending**. The editable
[PowerPoint and layout kit](../presentation/README.md) implement this framing with an 11-slide
core pitch, six Q&A slides and per-slide scripts in Notes. The current demo capture is explicitly
synthetic interface data; replace it with the selected real investigation before presenting a result.
This file preserves the team's framing and original candidate outline.

## Framing note (Rich, 2026-09-06)

I need to take a step back and understand this is not a bio crowd. So I need to explain why this is
amazing and high potential: talk about all the discoveries waiting to be found, and that compute, when
directed in the correct directions, can be highly impactful.

## What that means for the deck

- Lead with the idea, not the biology. The audience should leave understanding that published science
  is full of untested connections, and that an agent with a graph of the literature, public data, and
  a strict statistics gate can go test them at scale.
- Define every domain term the moment it appears (knowledge graph, claim, permutation test, DepMap).
  Assume no one knows what a cell line is.
- Show one concrete loop end to end: a claim in the literature, the agent noticing an untested bridge,
  code it wrote, the printed result, the falsifier's verdict, the human gate. One story, not a tour.
- Make the "compute pointed in the right direction" argument explicit: the bottleneck is not model
  capability, it is where you aim it and whether you trust what comes back. The graph aims it; the
  falsifier and the gate make it trustworthy.
- Be honest about what survival means. Survived verification is "the numbers are sound", never
  "this is true". A person decides truth at the gate. Non-bio audiences respect this more, not less.

## Candidate outline

1. The gap: how much of the literature is claims nobody has cross-checked against public data.
2. What we built, in one picture: literature to graph, agent roams it, writes experiments, statistics
   gate, human gate (the diagram in `ARCHITECTURE.md` section 1).
3. Live or recorded walkthrough of one investigation in the console.
4. Why the rigor layer matters: what the falsifier kills and why there is no answer key.
5. What is waiting to be found: scale of untested edges, cost per experiment, what more compute buys.
6. Limits and what is next.

## Open items

- Pick the one investigation to show; it needs a real candidate that reached the review queue.
- Decide live versus recorded playback for the console segment.
- Working format: native editable PowerPoint, approximately five-minute core pitch. Confirm the
  official pitch duration, final product name and entered category; the deck proposes Open Category
  based on the DTX-sponsored official category description.
