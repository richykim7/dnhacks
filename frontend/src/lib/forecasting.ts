export interface ForecastNode {
  id: string;
  label: string;
  type: string;
}
export interface ForecastClaim {
  id: string;
  source: string;
  target: string;
  relation: string;
  evidence_ids: string[];
  contexts?: {
    evidence_id?: string;
    disease?: string;
    disease_id?: string;
    clinical_significance?: string;
    direction?: string;
  }[];
}
export interface ForecastEvidence {
  id: string;
  title: string;
  text: string;
  url?: string;
  available_at?: string;
  publication_year?: number | null;
}
export interface ForecastCandidate {
  id: string;
  source: string;
  target: string;
  query_id: string;
}
export interface ForecastScenario {
  id: string;
  title: string;
  dataset: string;
  cutoff: string;
  horizon: string;
  nodes: ForecastNode[];
  claims: ForecastClaim[];
  evidence: ForecastEvidence[];
  candidates: ForecastCandidate[];
  manifest?: Record<string, unknown>;
}
export interface ForecastPrediction {
  candidate_id: string;
  score: number;
  evidence_ids?: string[];
  reason?: string;
  rank?: number;
  previous_rank?: number | null;
  rank_change?: number;
  paths?: { nodes: string[]; labels: string[]; evidence_ids: string[] }[];
}
export interface ForecastEvent {
  seq: number;
  type: string;
  revision: number;
  title: string;
  description: string;
  payload: Record<string, unknown>;
}
export interface ForecastRun {
  scenario_id: string;
  origin: string;
  model: string;
  policy: string;
  revisions?: {
    revision: number;
    evidence_ids: string[];
    forecasts: ForecastPrediction[];
    claim_count: number;
    node_count: number;
  }[];
  events: ForecastEvent[];
  forecasts: ForecastPrediction[];
  metrics?: Record<string, unknown>;
  costs?: Record<string, unknown>;
}
export interface ForecastOutcome {
  candidate_id: string;
  observed: boolean;
  evidence_ids: string[];
}
export interface ForecastPacket {
  scenario: ForecastScenario;
  run: ForecastRun;
  outcomes: ForecastOutcome[];
  future_evidence: ForecastEvidence[];
  report?: Record<string, unknown>;
  status?: string;
  artifact_url?: string;
}
const node = (id: string, label: string, type: string): ForecastNode => ({
  id,
  label,
  type,
});
const nodes = [
  node("braf", "BRAF", "gene"),
  node("egfr", "EGFR", "gene"),
  node("kras", "KRAS", "gene"),
  node("v600e", "V600E", "variant"),
  node("l858r", "L858R", "variant"),
  node("g12c", "G12C", "variant"),
  node("melanoma", "Melanoma", "disease"),
  node("lung", "Lung cancer", "disease"),
  node("colorectal", "Colorectal cancer", "disease"),
  node("therapy-a", "Therapy group A", "therapy"),
  node("therapy-b", "Therapy group B", "therapy"),
  node("therapy-c", "Therapy group C", "therapy"),
];
const edges = [
  ["braf", "v600e"],
  ["egfr", "l858r"],
  ["kras", "g12c"],
  ["v600e", "melanoma"],
  ["l858r", "lung"],
  ["g12c", "lung"],
  ["v600e", "colorectal"],
  ["melanoma", "therapy-a"],
  ["lung", "therapy-b"],
  ["colorectal", "therapy-c"],
  ["egfr", "colorectal"],
];
export const illustrativePacket: ForecastPacket = {
  scenario: {
    id: "illustrative-frontier",
    title: "Which biological connections deserve the next experiment?",
    dataset: "Illustrative biology workspace",
    cutoff: "2018-01-01",
    horizon: "2022-03-01",
    nodes,
    claims: edges.map(([source, target], i) => ({
      id: `claim-${i}`,
      source,
      target,
      relation: "illustrative connection",
      evidence_ids: [`source-${i % 3}`],
    })),
    evidence: [
      {
        id: "source-0",
        title: "A mechanism connects two neighborhoods",
        text: "Illustrative evidence card. The historical data provider will supply the source statement, biological context, and citation.",
      },
      {
        id: "source-1",
        title: "An independent observation adds context",
        text: "Illustrative evidence card. Shared source identities let the controller recognize overlap between research branches.",
      },
      {
        id: "source-2",
        title: "A new path changes the recommendation",
        text: "Illustrative evidence card. Predictions remain separate from established connections until later evidence is revealed.",
      },
    ],
    candidates: [
      {
        id: "prediction-a",
        source: "v600e",
        target: "therapy-b",
        query_id: "v600e",
      },
      {
        id: "prediction-b",
        source: "g12c",
        target: "therapy-c",
        query_id: "g12c",
      },
      {
        id: "prediction-c",
        source: "l858r",
        target: "therapy-a",
        query_id: "l858r",
      },
    ],
  },
  run: {
    scenario_id: "illustrative-frontier",
    origin: "illustrative",
    model: "Illustrative provider",
    policy: "Greedy evidence coverage",
    events: [],
    forecasts: [
      {
        candidate_id: "prediction-a",
        score: 3,
        reason: "A new evidence path connects these neighborhoods.",
      },
      {
        candidate_id: "prediction-b",
        score: 2,
        reason: "This branch explores evidence outside the first branch.",
      },
      {
        candidate_id: "prediction-c",
        score: 1,
        reason: "A competing path remains available for comparison.",
      },
    ],
  },
  outcomes: [
    { candidate_id: "prediction-a", observed: true, evidence_ids: [] },
    { candidate_id: "prediction-b", observed: false, evidence_ids: [] },
    { candidate_id: "prediction-c", observed: true, evidence_ids: [] },
  ],
  future_evidence: [],
};
