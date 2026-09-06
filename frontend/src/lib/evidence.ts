import type { Graph } from "./types";

export type ClaimEdge = Graph["edges"][number] & {
  claim_id?: string;
  object_function?: string;
  polarity?: number;
  dispute_kind?: string;
};
export type EvidenceGraph = Omit<Graph, "edges"> & { edges: ClaimEdge[] };
export interface Paper {
  paper_id: string;
  title?: string;
  year?: number;
  doi?: string;
  pmid?: string;
  url?: string;
  meta_verified?: boolean | null;
}
export interface ClaimDetail {
  source: string;
  claim: {
    claim_id: string;
    subject_label: string;
    object_label: string;
    predicate: string;
    polarity?: number;
    status: string;
    dispute_kind?: string;
    mechanism?: string;
  };
  evidence_total: number;
  evidence: {
    evidence_id: number;
    source_ref: number;
    source_label?: string;
    quote?: string;
    section?: string;
    study_type?: string;
    evidence_type?: string;
    attribution?: string;
    certainty?: string;
    papers: Paper[];
    contexts: {
      ctx_id: number;
      slot: string;
      label?: string;
      value: string;
      provenance?: string;
      quote?: string;
    }[];
  }[];
}
export function paperLink(paper: Paper): string | undefined {
  if (paper.doi?.startsWith("10."))
    return `https://doi.org/${encodeURI(paper.doi)}`;
  if (paper.pmid && /^\d+$/.test(paper.pmid))
    return `https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`;
  try {
    const url = new URL(paper.url || "");
    if (url.protocol === "https:" || url.protocol === "http:") return url.href;
  } catch {
    /* Missing or invalid metadata has no external link. */
  }
}
