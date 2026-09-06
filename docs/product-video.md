# Product walkthrough

The Remotion project lives in [`video/`](../video/README.md). It renders a 138-second
1080p walkthrough from opening the research library through collection setup,
paper arrivals, graph construction, investigation branching, and candidate review.
The first two researcher inspections are deliberately slow; later branches speed
up while the camera zooms out. A visible cursor and written captions guide the flow.

The video reuses shared frontend components and generated native application styles,
with separate frame-driven scene state. It does not operate the app or execute
research. Real bibliographic metadata comes from the committed PDAC curation;
graph growth and research activity are authored illustrative sequences.

The default ending explicitly leaves the held-out paper reveal pending. Supply the
verified matching paper, candidate, run identifier, corpus manifest hash and access
boundary before producing the final discovery version. The paper appears first;
the next scene explains the frozen evidence boundary, following the demo narrative.
A frozen corpus alone does not eliminate pretrained model knowledge.

See the video README for preview/render commands and the Playwright frame-review
workflow, which shares the repository browser queue and owns its isolated server.
No deployment or live data changes are part of this video workflow.
