// Types and vocabulary for the Knowledge view. Every label here names a value the engine's closed
// vocabularies can actually write (litmap/vocab.py, litmap/store.py, falsifier.py); nothing is
// invented on the way to the screen, and a value outside the vocabulary falls back to its raw text.
export interface Tested {
  n: number;
  candidate: number;
  validated: number;
  rejected: number;
  killed: number;
}
export interface GraphNode {
  id: string;
  label: string;
  curie?: string;
  kind?: string;
  degree: number;
  n_out?: number;
  n_in?: number;
}
export interface ClaimEdge {
  claim_id?: string;
  abstract_key?: string;
  source: string;
  target: string;
  predicate: string;
  object_function?: string;
  relation_class?: string;
  polarity?: number;
  mechanism?: string;
  status: string;
  dispute_kind?: string;
  n_sources: number;
  first_year?: number | null;
  confidence?: number;
  tested?: Tested | null;
}
export interface Facet {
  value: string | number;
  n: number;
}
export interface CollectionSummary {
  claims: number;
  entities: number;
  evidence: number | null;
  papers: number | null;
  papers_full_text: number | null;
  experiments: number | null;
  deferrals: number | null;
  tests: number | null;
  vectors: number | null;
}
export interface EvidenceGraph {
  source?: string;
  sources: string[];
  nodes: GraphNode[];
  edges: ClaimEdge[];
  shown?: number;
  complete?: boolean;
  loaded_entities?: number;
  matched?: number;
  total_claims?: number;
  status_counts?: Record<string, number>;
  facets?: Record<string, Facet[]>;
  summary?: CollectionSummary;
  as_of?: number | null;
}
export interface Paper {
  paper_id: string;
  source_ref?: number;
  source_label?: string;
  title?: string;
  year?: number;
  doi?: string;
  pmid?: string;
  pmcid?: string;
  url?: string;
  license?: string;
  is_full_text?: boolean | null;
  n_chars?: number | null;
  meta_method?: string;
  meta_verified?: boolean | null;
}
export interface Experiment {
  experiment_id: string;
  unit?: string;
  intervention?: string;
  control?: string;
  readout?: string;
  assay?: string;
  timepoint?: string;
  n?: number | null;
  effect?: string;
  uncertainty?: string;
  statistic?: string;
  quote?: string;
}
export interface Cite {
  sid: string;
  marker?: string;
  tier?: string;
}
export interface Context {
  ctx_id: number;
  slot: string;
  value: string;
  label?: string;
  provenance?: string;
  quote?: string;
  inherited_from?: string;
}
export interface EvidenceRecord {
  evidence_id: number;
  source_ref: number;
  source_label?: string;
  experiment_id?: string | null;
  quote?: string;
  section?: string;
  predicate?: string;
  aspect_said?: string;
  mechanism_term?: string;
  quantifier?: string;
  evidence_type?: string;
  study_type?: string;
  attribution?: string;
  attribution_basis?: string;
  attribution_agreed?: boolean | null;
  certainty?: string;
  certainty_basis?: string;
  certainty_agreed?: boolean | null;
  extractor?: string;
  prompt_version?: string;
  papers: Paper[];
  contexts: Context[];
  cites?: Cite[];
  experiment?: Experiment | null;
}
export interface EngineTest {
  test_id: number;
  run_id: string;
  method?: string;
  hypothesis?: string;
  expected_sign?: number | null;
  observed_sign?: number | null;
  effect?: number | null;
  effect_size?: number | null;
  p_null?: number | null;
  status: string;
  kill_reason?: string;
  verdict_note?: string;
  human_review?: string;
  review_note?: string;
  novelty_verdict?: string;
  created_at?: string;
}
export interface RelatedClaim {
  claim_id: string;
  subject_label: string;
  predicate: string;
  object_label: string;
  object_function?: string;
  relation_class?: string;
  polarity?: number;
  status: string;
  dispute_kind?: string;
  n_sources: number;
  first_year?: number | null;
}
export interface EntityForm {
  state?: string;
  variant?: string;
  isoform?: string;
  protein_construct?: string;
  feature_type?: string;
  feature_tier?: string;
}
export interface ClaimDetail {
  source: string;
  claim: {
    claim_id: string;
    abstract_key?: string;
    subject_id?: string;
    subject_label: string;
    subject_curie?: string;
    subject_kind?: string;
    subject_form?: EntityForm;
    object_id?: string;
    object_label: string;
    object_curie?: string;
    object_kind?: string;
    object_form?: EntityForm;
    predicate: string;
    object_function?: string;
    relation_class?: string;
    polarity?: number;
    mechanism?: string;
    status: string;
    dispute_kind?: string;
    n_sources?: number;
    first_year?: number | null;
    confidence?: number;
    created_at?: string;
  };
  evidence_total: number;
  evidence: EvidenceRecord[];
  related?: RelatedClaim[];
  tests?: EngineTest[];
}

// --- links ------------------------------------------------------------------------------------
export function paperLink(paper: Paper): string | undefined {
  return paperLinks(paper)[0]?.href;
}
export function paperLinks(paper: Paper): { label: string; href: string }[] {
  const out: { label: string; href: string }[] = [];
  if (paper.doi?.startsWith("10."))
    out.push({ label: "DOI", href: `https://doi.org/${encodeURI(paper.doi)}` });
  if (paper.pmid && /^\d+$/.test(paper.pmid))
    out.push({
      label: "PubMed",
      href: `https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`,
    });
  if (paper.pmcid && /^PMC\d+$/i.test(paper.pmcid))
    out.push({
      label: "PMC",
      href: `https://www.ncbi.nlm.nih.gov/pmc/articles/${paper.pmcid.toUpperCase()}/`,
    });
  if (!out.length) {
    try {
      const url = new URL(paper.url || "");
      if (url.protocol === "https:" || url.protocol === "http:")
        out.push({ label: "Source", href: url.href });
    } catch {
      /* Missing or invalid metadata has no external link. */
    }
  }
  return out;
}
// A CURIE resolves through Bioregistry, which knows every namespace the grounder can emit
// (HGNC, GO, MONDO, HP, UBERON, CL, CHEBI, SO, NCBITaxon, Cellosaurus...). Anything else is text.
export function curieLink(curie?: string): string | undefined {
  if (!curie) return;
  const m = /^([A-Za-z][A-Za-z0-9.]*)[:_]([A-Za-z0-9._-]+)$/.exec(curie.trim());
  if (!m) return;
  return `https://bioregistry.io/${encodeURIComponent(m[1].toLowerCase())}:${encodeURIComponent(m[2])}`;
}

// --- closed vocabularies ---------------------------------------------------------------------
export const KIND_LABEL: Record<string, string> = {
  entity: "Gene, protein or chemical",
  process: "Biological process",
  pathological_process: "Pathological process",
  disease: "Disease",
  phenotype: "Phenotype",
  mark: "Chromatin mark",
  repeat_family: "Repeat family",
  feature: "Genomic feature",
  anatomy: "Anatomy",
  cell_type: "Cell type",
  cell_line: "Cell line",
  organism: "Organism",
  endpoint: "Clinical endpoint",
};
export type KindShape =
  "circle" | "diamond" | "square" | "hexagon" | "triangle" | "bar" | "ring";
export function kindShape(kind?: string): KindShape {
  switch (kind) {
    case "entity":
      return "circle";
    case "process":
    case "pathological_process":
      return "diamond";
    case "disease":
    case "phenotype":
      return "square";
    case "anatomy":
    case "cell_type":
    case "cell_line":
    case "organism":
      return "hexagon";
    case "mark":
    case "feature":
    case "repeat_family":
      return "triangle";
    case "endpoint":
      return "bar";
    default:
      return "ring";
  }
}
export function kindLabel(kind?: string): string {
  return kind ? KIND_LABEL[kind] || humanize(kind) : "Kind not recorded";
}

// Polarity is the sign the predicate carries: +1 enabling, -1 repressive, 0 undirected.
export function polarityLabel(polarity?: number | null): string {
  return polarity === 1
    ? "Enabling"
    : polarity === -1
      ? "Repressive"
      : polarity === 0
        ? "Undirected"
        : "Not recorded";
}
export function polarityMarker(
  polarity?: number | null,
): "arrow" | "tee" | "dot" {
  return polarity === 1 ? "arrow" : polarity === -1 ? "tee" : "dot";
}
export function relationLabel(relationClass?: string): string {
  return (
    {
      causal: "Causal",
      correlational: "Correlational",
      temporal: "Temporal",
      predictive: "Predictive",
    }[relationClass || ""] || "Unclassed"
  );
}
export function signGlyph(sign?: number | null): string {
  return sign === 1 ? "+" : sign === -1 ? "−" : sign === 0 ? "0" : "·";
}

// The status vocabulary and what each word may and may not mean (docs/architecture knowledge
// contract): source-count status, never approval or proof.
export function statusExplanation(
  status: string,
  disputeKind?: string,
): string {
  switch (status) {
    case "established":
      return "Two or more distinct sources in this collection assert it. A source count, not a review or a proof.";
    case "reported":
      return "One source in this collection asserts it.";
    case "disputed":
      return `Another claim in this collection answers the same question differently${
        disputeKind ? ` (${humanize(disputeKind).toLowerCase()})` : ""
      }.`;
    default:
      return "";
  }
}
export function statusTone(status: string): string {
  return status === "disputed" ? "attention" : "neutral";
}
export const DISPUTE_LABEL: Record<string, string> = {
  opposite_sign: "Opposite sign",
  opposite_predicate: "Opposite predicate",
  measured_null: "Measured null",
  direct: "Direct contradiction",
};
export const EVIDENCE_TYPE_LABEL: Record<string, string> = {
  experimental_own: "Own experiment",
  author_statement_prior: "Authors citing prior work",
  computational_inference: "Computational inference",
  curator_inference: "Curator inference",
  unspecified: "Unspecified",
};
export const STUDY_TYPE_LABEL: Record<string, string> = {
  molecular_experiment: "Molecular experiment",
  genomic_assay: "Genomic assay",
  cohort_association: "Cohort association",
  clinical_trial: "Clinical trial",
  animal_experiment: "Animal experiment",
  evolutionary_comparison: "Evolutionary comparison",
  computational_analysis: "Computational analysis",
  review_statement: "Review statement",
  unspecified: "Unspecified",
};
export function attributionLabel(attribution?: string): string {
  return attribution === "own"
    ? "This source's own finding"
    : attribution === "prior"
      ? "This source citing prior work"
      : "Attribution unclear";
}
export const CERTAINTY_LABEL: Record<string, string> = {
  demonstrated: "Demonstrated",
  suggested: "Suggested",
  predicted: "Predicted",
  hypothesized: "Hypothesized",
};
export const PROVENANCE_LABEL: Record<string, string> = {
  stated: "Stated with the claim",
  inherited: "Inherited from elsewhere in the paper",
  unspecified: "Not stated",
};
// falsifier.py kill slugs, spelled out.
export const KILL_LABEL: Record<string, string> = {
  "no-effect": "No finite effect reported",
  "malformed-p": "p-value is not a probability",
  "malformed-result": "Result missing required fields",
  "too-few-units": "Fewer than 8 independent units",
  "not-significant": "p above 0.05",
  "direction-wrong": "Direction opposite to prediction",
  "not-robust": "Failed the robustness check",
};
export interface TestOutcome {
  label: string;
  tone: "neutral" | "attention" | "negative" | "live";
  detail: string;
}
export function testOutcome(test: EngineTest): TestOutcome {
  if (test.human_review === "validated")
    return {
      label: "Accepted by reviewer",
      tone: "live",
      detail: test.review_note || "No review note stored.",
    };
  if (test.human_review === "rejected")
    return {
      label: "Rejected by reviewer",
      tone: "negative",
      detail: test.review_note || "No review note stored.",
    };
  if (test.status === "candidate")
    return {
      label: "Passed verifier checks",
      tone: "attention",
      detail:
        "Awaiting a person's decision. Sound numbers, not an accepted finding.",
    };
  return {
    label: "Failed verification",
    tone: "negative",
    detail:
      KILL_LABEL[test.kill_reason || ""] ||
      test.verdict_note ||
      humanize(test.status),
  };
}
export const NOVELTY_LABEL: Record<string, string> = {
  known: "Already in the literature graph",
  contradicts: "Contradicts the literature graph",
  "distant-field": "Bridges distant fields",
  open: "Not covered by the literature graph",
};

// --- presentation helpers -------------------------------------------------------------------
export function humanize(value?: string | null): string {
  return value
    ? value.replace(/[_-]/g, " ").replace(/^\w/, (c) => c.toUpperCase())
    : "Not recorded";
}
export function edgeWidth(nSources: number): number {
  return nSources >= 4 ? 2.6 : nSources >= 2 ? 1.8 : 1.2;
}
export function claimKey(edge: ClaimEdge): string {
  return (
    edge.claim_id ||
    JSON.stringify([edge.source, edge.predicate, edge.target, edge.status])
  );
}
export function claimSentence(
  edge: Pick<ClaimEdge, "source" | "target" | "predicate" | "object_function">,
  labels: Map<string, string>,
): string {
  const subject = labels.get(edge.source) || edge.source;
  const object = labels.get(edge.target) || edge.target;
  const aspect = edge.object_function
    ? ` (${humanize(edge.object_function).toLowerCase()})`
    : "";
  return `${subject} ${humanize(edge.predicate).toLowerCase()} ${object}${aspect}`;
}
export function asOf(value?: number | null): string {
  return value
    ? new Date(value * 1000).toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "time not recorded";
}
