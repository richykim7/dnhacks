// Timings are authored presentation time, never research execution measurements.
export const FPS = 30;
export const chapters = [
  { id: "Welcome", title: "Start with a field of literature", seconds: 8 },
  { id: "Project", title: "Define the collection", seconds: 17 },
  { id: "Library", title: "Turn papers into a research library", seconds: 17 },
  { id: "Knowledge", title: "Connect the evidence", seconds: 18 },
  { id: "Question", title: "Ask a research question", seconds: 12 },
  { id: "Investigation", title: "Follow the investigation", seconds: 36 },
  { id: "Review", title: "Inspect the candidate", seconds: 12 },
  { id: "Reveal", title: "The held-out paper", seconds: 10 },
  { id: "Boundary", title: "What the investigator could see", seconds: 8 },
] as const;
export const totalFrames = chapters.reduce((n, c) => n + c.seconds * FPS, 0);
export type RevealData = {
  paperTitle: string;
  doi: string;
  publicationDate: string;
  candidate: string;
  runId: string;
  manifestHash: string;
  evidenceNote: string;
  verified: boolean;
};
export const pendingReveal: RevealData = {
  paperTitle: "",
  doi: "",
  publicationDate: "",
  candidate: "",
  runId: "",
  manifestHash: "",
  evidenceNote: "",
  verified: false,
};
export const renderReady = (r: RevealData) =>
  r.verified &&
  [
    r.paperTitle,
    r.doi,
    r.publicationDate,
    r.candidate,
    r.runId,
    r.manifestHash,
    r.evidenceNote,
  ].every((x) => x.trim().length > 0);
