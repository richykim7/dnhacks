export type JsonRecord = Record<string, any>;
export interface Beam {
  angle?: string;
  adversarial?: boolean;
  kept?: boolean;
  rank?: number;
  reason?: string;
}
export interface RunSummary {
  runtime?: boolean;
  lifecycle?: string;
  objective?: string;
  run_id: string;
  root: string;
  parent: string | null;
  depth: number;
  steps: number;
  active: boolean;
  last_action: string;
  updated_at: number;
  beam?: Beam;
  project?: string;
}
export interface Investigation {
  runtime?: boolean;
  root: string;
  runs: RunSummary[];
  active: boolean;
  last_action: string;
  updated_at: number;
  n_runs: number;
  n_branches: number;
}
export interface Step {
  step: number;
  action: string;
  phase?: string;
  ts?: number;
  dt_s?: number;
  reasoning?: string;
  thinking?: string;
  observation?: string;
  args?: JsonRecord;
  fork?: JsonRecord;
}
export interface RunDetail extends Omit<RunSummary, "steps"> {
  n_steps: number;
  resume_line: number;
  steps: Step[];
  tests: JsonRecord[];
  tallies: JsonRecord;
}
export interface Experiment {
  entry_id: number;
  run_id: string;
  kind: string;
  title: string;
  body?: string;
  code?: string;
  result?: JsonRecord;
  output?: string;
  provenance?: JsonRecord;
  stage: string;
  status: string;
  subject?: string;
  object?: string;
  method?: string;
  effect?: number;
  p_null?: number;
  robust?: boolean;
  n_units?: number;
  failed?: boolean;
  raised?: boolean;
  retry_of?: number;
  verdict?: string;
  kill_reason?: string;
  verdict_note?: string;
}
export interface TreeData {
  root: string;
  lanes: {
    run_id: string;
    parent: string | null;
    depth: number;
    n_experiments: number;
  }[];
  nodes: Experiment[];
  forks: JsonRecord[];
  fans: JsonRecord[];
  orphans: JsonRecord[];
  unverified_submissions: number[];
  db_unreadable: string;
  counts: Record<string, number>;
}
export interface Project {
  id: string;
  name: string;
  description?: string;
  adopted: boolean;
  status: string;
  has_kg?: boolean;
  kg_db?: string;
  n_claims?: number | null;
  spec: JsonRecord;
  chat?: JsonRecord[];
  built?: JsonRecord;
  build?: JsonRecord;
}
export interface Graph {
  sources: string[];
  nodes: { id: string; label: string; degree: number; function?: string }[];
  edges: {
    source: string;
    target: string;
    predicate: string;
    status: string;
    n_sources: number;
    confidence: number;
  }[];
  shown?: number;
  total_claims?: number;
  source?: string;
}
