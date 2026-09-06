# Demo slides

Status: **revised editable deck; scientific reveal still pending**. The
[PowerPoint, judge-pitch PDF, reviewer copy and layout kit](../presentation/README.md)
now lead with strategic biological anticipation, show real 3D software artifacts and measured
training/evaluation results, and address the full rubric. Slides 10–13 preserve the exact complete-loop,
survivors, paper-fade and frozen-corpus-next-slide sequence as hidden, explicitly unpopulated
storyboards. Enable only after selecting and verifying a qualifying run and excluded matching paper.
Every slide has a tentative script in Notes; technical appendices distinguish measured training
histories from final held-out comparisons and untrained components.

The ordinary falsifier screens reported result fields and flags; it does not independently certify
that arbitrary numerical outputs are sound. Human review records a decision, not biological truth.
This is the precise implementation boundary for the earlier framing shorthand below.

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

## Experimental-loop reveal narrative (Rich, 2026-09-06)

I want to walk the audience through a full experimental loop, then reveal what one of the surviving
candidates amounted to. This could be a video, slides, or a mix; the format is still undecided.

1. Walk through the steps of one complete investigation: the literature claim, the untested bridge,
   the experiment and code, the result, verification, and human review. Show snapshots at different
   steps, relevant renderings, and selected agent reasoning or explanations of its decisions so the
   audience can follow why it took each next step.
2. Show the candidates that made it through the loop. Let the audience understand the surviving
   candidates before revealing the outcome of one of them.
3. End the walkthrough with the reveal: one candidate corresponds to a novel discovery. Show the
   paper reporting that discovery fading into view on the slide, making the connection between the
   candidate and the published finding clear.
4. On the **next slide, after the paper reveal**, explain the frozen corpus: what literature and data
   the agent could access, the cutoff, and how the revealed paper was held outside that evidence.
   The intended payoff is that the audience first sees the loop work, then understands why recovering
   that later finding from earlier evidence is compelling.

This is the desired narrative, not a claim that a qualifying run has already been demonstrated. Select
and verify the candidate, matching paper, dates, and actual evidence boundary before presenting the
reveal. Describe a later published discovery recovered from frozen evidence as such; passing the
verification gate alone does not establish novelty or truth, and a frozen corpus alone does not rule
out model prior knowledge. Keep the existing distinction between candidates and confirmed findings.

## Technical toolkit coverage (Rich, 2026-09-06)

Also explain the computational toolkit, leading with the tools that have 3D renderings. The internal
e-value tools are part of that toolkit; cover them explicitly, along with the e-value branch-monitoring
tool. For each learned component, explain how we trained it: data, model, objective, training/validation
split, and what it learns or measures. Distinguish trained components from statistical logic and
rendering code. Have real training/validation loss curves ready, plus useful technical figures such as
null calibration, power, evidence trajectories, or baseline comparisons, so the academic and technical
substance is clear. This plot emphasis is mainly for the e-value components; the 3D tools should lead
with renderings and experiment outputs. Label each figure's run, dataset, and measured versus planned
status; do not imply an untrained component was trained. This is a deck-content and asset-preparation
note, not authorization to start new training runs.

## Candidate outline

1. The gap: how much of the literature is claims nobody has cross-checked against public data.
2. What we built, in one picture: literature to graph, agent roams it, writes experiments, statistics
   gate, human gate (the diagram in `ARCHITECTURE.md` section 1).
3. Full experimental-loop walkthrough with snapshots, renderings, and agent decision explanations;
   show the surviving candidates, then reveal the matching discovery paper with a fade-in.
4. Immediately following the reveal, explain the frozen corpus and evidence cutoff. Explain why the
   rigor layer matters: what the falsifier kills and why survival is not proof of truth.
5. What is waiting to be found: scale of untested edges, cost per experiment, what more compute buys.
6. Limits and what is next.

## Open items

- Pick the one investigation to show; it needs a real candidate that reached the review queue.
- Decide live versus recorded playback for the console segment.
- Decide video versus slides (or a mix) for the loop and paper reveal; collect the step snapshots,
  renderings, and agent decision excerpts from the selected run.
- Select the discovery paper and verify its match to a surviving candidate and exclusion from the
  run's accessible evidence; document the cutoff and remaining model-prior-knowledge limitations.
- Working format: native editable PowerPoint, approximately five-minute core pitch. Confirm the
  official pitch duration, final product name and entered category; the deck proposes Open Category
  based on the DTX-sponsored official category description.
