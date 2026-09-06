import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  ReactFlowProvider,
  useReactFlow,
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { ArrowLeft, ArrowUpRight, ListFilter, Search, X } from "lucide-react";
import dagre from "@dagrejs/dagre";
import {
  paperLink,
  type ClaimDetail,
  type ClaimEdge,
  type EvidenceGraph,
} from "@/lib/evidence";
import "../evidence.css";
import { useResource } from "@/lib/api";
import { human, id, number } from "@/lib/utils";
import { Button } from "./ui/button";
import { Disclosure, Empty, ErrorNotice, Loading, Status } from "./common";

function EntityNode({
  data,
}: NodeProps<Node<{ label: string; degree: number; selected: boolean }>>) {
  return (
    <div className={`entity-node ${data.selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <span className="entity-dot" />
      <strong>{data.label}</strong>
      <small>
        {data.degree} {data.degree === 1 ? "connection" : "connections"}
      </small>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { entity: EntityNode };
export function Knowledge({ project }: { project: string }) {
  return (
    <div className="evidence-page">
      <header className="page-heading">
        <div>
          <div className="breadcrumb">Research workspace / Knowledge</div>
          <h1>Explore knowledge</h1>
          <p>
            Explore literature relationships and inspect their supporting
            sources.
          </p>
        </div>
      </header>
      <Relationships key={project} project={project} />
    </div>
  );
}
function FocusEvidence({ ids }: { ids: string }) {
  const flow = useReactFlow();
  useEffect(() => {
    if (!ids) return;
    const timer = setTimeout(
      () =>
        void flow.fitView({
          nodes: JSON.parse(ids).map((nodeId: string) => ({ id: nodeId })),
          padding: 0.45,
          maxZoom: 1,
          duration: matchMedia("(prefers-reduced-motion: reduce)").matches
            ? 0
            : 250,
        }),
      100,
    );
    return () => clearTimeout(timer);
  }, [ids, flow]);
  return null;
}
function ClaimSources({
  source,
  claimId,
}: {
  source: string;
  claimId?: string;
}) {
  const detail = useResource<ClaimDetail>(
    claimId && source
      ? `/api/kg?source=${id(source)}&claim=${id(claimId)}`
      : null,
  );
  if (!claimId)
    return (
      <p className="muted">
        Source inspection is unavailable for this older graph response. Refresh
        after updating the server.
      </p>
    );
  return (
    <section className="claim-sources" aria-label="Supporting evidence">
      <h3>What supports this relationship?</h3>
      <ErrorNotice message={detail.error} retry={detail.refresh} />
      {detail.loading && <Loading label="Loading source evidence" />}
      {detail.data?.claim.mechanism && (
        <p className="claim-mechanism">{detail.data.claim.mechanism}</p>
      )}
      {detail.data && (
        <p className="muted">
          {detail.data.evidence.length} of {detail.data.evidence_total} stored
          evidence records. Source statements retain their original context.
        </p>
      )}
      {detail.data?.evidence.length === 0 && (
        <p>No quoted evidence is stored for this relationship.</p>
      )}
      {detail.data?.evidence.map((e) => (
        <article className="source-evidence" key={e.evidence_id}>
          <header>
            <span className="source-ref">Source {e.source_ref}</span>
            <span>{e.section || "Section not recorded"}</span>
          </header>
          {e.papers.length ? (
            e.papers.map((p) => (
              <div className="source-paper" key={p.paper_id}>
                <h4>{p.title || e.source_label || "Untitled source"}</h4>
                <span>{p.year || "Year not recorded"}</span>
                {paperLink(p) && (
                  <a href={paperLink(p)} target="_blank" rel="noreferrer">
                    Open paper <ArrowUpRight size={13} />
                  </a>
                )}
                {p.meta_verified === false && (
                  <small>Source identity has not been verified.</small>
                )}
              </div>
            ))
          ) : (
            <h4>{e.source_label || "Source metadata not stored"}</h4>
          )}
          {e.quote ? (
            <blockquote>{e.quote}</blockquote>
          ) : (
            <p className="muted">No source quotation stored.</p>
          )}
          <div className="evidence-attributes">
            <span>
              {e.attribution === "own"
                ? "Attributed to this source"
                : e.attribution === "prior"
                  ? "Source cites prior work"
                  : "Attribution unclear"}
            </span>
            {e.certainty && <span>Source assertion: {human(e.certainty)}</span>}
            {e.study_type && e.study_type !== "unspecified" && (
              <span>{human(e.study_type)}</span>
            )}
            {e.evidence_type && e.evidence_type !== "unspecified" && (
              <span>{human(e.evidence_type)}</span>
            )}
          </div>
          {e.contexts.length > 0 && (
            <details className="source-context" open>
              <summary>Biological context</summary>
              <dl>
                {e.contexts.map((c) => (
                  <div key={c.ctx_id}>
                    <dt>{human(c.slot)}</dt>
                    <dd>
                      {c.label || c.value}
                      <small>{human(c.provenance || "unspecified")}</small>
                      {c.quote && <q>{c.quote}</q>}
                    </dd>
                  </div>
                ))}
              </dl>
            </details>
          )}
        </article>
      ))}
    </section>
  );
}
function Relationships({ project }: { project: string }) {
  const [source, setSource] = useState(project);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const [claimKey, setClaimKey] = useState("");
  const [browse, setBrowse] = useState(false);
  const graph = useResource<EvidenceGraph>(
    `/api/kg?limit=120${source ? `&source=${id(source)}` : ""}${status ? `&status=${id(status)}` : ""}`,
    15000,
  );
  const data = graph.data;
  const labels = useMemo(
    () => new Map(data?.nodes.map((n) => [n.id, n.label])),
    [data],
  );
  const keyFor = (e: ClaimEdge) =>
    e.claim_id || JSON.stringify([e.source, e.predicate, e.target, e.status]);
  const sentence = (e: ClaimEdge) =>
    `${labels.get(e.source) || e.source} ${human(e.predicate).toLowerCase()} ${labels.get(e.target) || e.target}${e.object_function ? ` · ${human(e.object_function)}` : ""}`;
  const claim = data?.edges.find((e) => keyFor(e) === claimKey);
  const entity = data?.nodes.find((n) => n.id === selected);
  const matches = (e: ClaimEdge) =>
    sentence(e).toLowerCase().includes(query.trim().toLowerCase());
  const related =
    data?.edges.filter(
      (e) =>
        (!selected || e.source === selected || e.target === selected) &&
        matches(e),
    ) || [];
  const focused = new Set(
    claim
      ? [claim.source, claim.target]
      : selected
        ? [selected, ...related.flatMap((e) => [e.source, e.target])]
        : [],
  );
  const focusIds = focused.size ? JSON.stringify([...focused].sort()) : "";
  const positions = useMemo(() => {
    const layout = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    layout.setGraph({ rankdir: "LR", nodesep: 55, ranksep: 150 });
    data?.nodes.forEach((n) =>
      layout.setNode(n.id, { width: 220, height: 76 }),
    );
    data?.edges.forEach((e) => layout.setEdge(e.source, e.target));
    dagre.layout(layout);
    return new Map(
      data?.nodes.map((n) => {
        const point = layout.node(n.id);
        return [n.id, { x: point.x - 110, y: point.y - 38 }];
      }),
    );
  }, [data]);
  const nodes =
    data?.nodes.map((n) => ({
      id: n.id,
      type: "entity",
      position: positions.get(n.id)!,
      data: { ...n, selected: focused.has(n.id) },
    })) || [];
  const edges =
    data?.edges.map((e) => {
      const active = claim
        ? keyFor(e) === claimKey
        : selected
          ? e.source === selected || e.target === selected
          : false;
      const dim = (claimKey || selected) && !active;
      const color =
        e.status === "disputed"
          ? "var(--attention)"
          : active
            ? "var(--accent)"
            : "var(--edge)";
      return {
        id: keyFor(e),
        source: e.source,
        target: e.target,
        label:
          active || data.edges.length <= 12
            ? human(e.predicate).toLowerCase()
            : undefined,
        ariaLabel: `${sentence(e)}. ${human(e.status)}. Inspect evidence`,
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: {
          stroke: color,
          strokeWidth: active ? 2 : 1,
          opacity: dim ? 0.15 : 0.8,
          strokeDasharray: e.status === "disputed" ? "5 4" : undefined,
        },
        labelStyle: { fill: "var(--fg)", fontSize: 12 },
        labelBgStyle: { fill: "var(--surface)" },
        labelBgPadding: [7, 4] as [number, number],
        labelBgBorderRadius: 4,
      };
    }) || [];
  const inspect = (e: ClaimEdge) => {
    setClaimKey(keyFor(e));
    setBrowse(true);
  };
  const clear = () => {
    setSelected("");
    setClaimKey("");
    setBrowse(false);
  };
  return (
    <>
      <div className="evidence-toolbar">
        <label className="search-field">
          <Search size={15} />
          <input
            placeholder="Find an entity or relationship"
            aria-label="Find an entity or relationship"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setClaimKey("");
              setSelected("");
              setBrowse(true);
            }}
          />
        </label>
        {!project && (
          <label>
            Collection
            <select
              aria-label="Knowledge collection"
              value={source || data?.source || ""}
              onChange={(e) => {
                setSource(e.target.value);
                clear();
              }}
            >
              {data?.sources.map((s) => (
                <option key={s} value={s}>
                  {human(s.replace("project:", ""))}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Claims
          <select
            aria-label="Claim status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              clear();
            }}
          >
            <option value="">All statuses</option>
            <option value="disputed">Disputed</option>
            <option value="established">Established</option>
            <option value="reported">Reported</option>
          </select>
        </label>
        <span className="muted">
          {data?.shown != null
            ? `${data.shown} of ${number(data.total_claims)} claims shown`
            : ""}
        </span>
      </div>
      <ErrorNotice message={graph.error} retry={graph.refresh} />
      {graph.loading ? (
        <Loading />
      ) : !data?.nodes.length ? (
        <Empty title="No relationships to explore yet">
          Build a literature collection to connect its claims and entities.
        </Empty>
      ) : (
        <div
          className={`relationships-layout evidence-explorer ${browse ? "browsing" : ""}`}
        >
          <div className="relationship-canvas">
            <div className="evidence-map-caption">
              <strong>Literature relationships</strong>
              <span>Select a connection to read its evidence.</span>
            </div>
            <ReactFlowProvider>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
                minZoom={0.1}
                maxZoom={2}
                nodesConnectable={false}
                onNodeClick={(_, n) => {
                  setSelected(n.id);
                  setClaimKey("");
                  setBrowse(true);
                }}
                onEdgeClick={(_, e) => {
                  const found = data.edges.find((c) => keyFor(c) === e.id);
                  if (found) inspect(found);
                }}
                onPaneClick={clear}
              >
                <FocusEvidence ids={focusIds} />
                <Background gap={24} size={0.6} color="var(--grid)" />
                <Controls showInteractive={false} />
              </ReactFlow>
            </ReactFlowProvider>
            <div className="evidence-legend">
              <span>→ Direction of claim</span>
              <span className="disputed-key">┄ Disputed in corpus</span>
            </div>
            <Button className="browse-evidence" onClick={() => setBrowse(true)}>
              <ListFilter size={15} />
              Browse {related.length} relationships
            </Button>
          </div>
          <aside
            className="detail-panel evidence-inspector"
            aria-label="Relationship evidence"
          >
            <div className="detail-head">
              <span>
                {claim
                  ? "Relationship evidence"
                  : entity
                    ? "Entity connections"
                    : "Browse relationships"}
              </span>
              {(claim || selected || browse) && (
                <Button
                  aria-label="Close entity detail"
                  variant="ghost"
                  size="icon"
                  onClick={clear}
                >
                  <X size={16} />
                </Button>
              )}
            </div>
            <div className="detail-scroll">
              {claim ? (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="back-to-claims"
                    onClick={() => setClaimKey("")}
                  >
                    <ArrowLeft size={14} />
                    Back to connections
                  </Button>
                  <Status
                    label={human(claim.status)}
                    tone={claim.status === "disputed" ? "attention" : "neutral"}
                  />
                  <h2 className="selected-claim-title">{sentence(claim)}</h2>
                  <p className="muted">
                    {claim.n_sources}{" "}
                    {claim.n_sources === 1 ? "source" : "sources"} in this
                    collection. Status describes the corpus claim, not
                    independent verification.
                  </p>
                  {claim.dispute_kind && (
                    <p className="notice">
                      Dispute: {human(claim.dispute_kind)}
                    </p>
                  )}
                  <div className="claim-endpoints">
                    {[...new Set([claim.source, claim.target])].map(
                      (endpoint) => (
                        <button
                          key={endpoint}
                          onClick={() => {
                            setSelected(endpoint);
                            setClaimKey("");
                          }}
                        >
                          {labels.get(endpoint)}
                          <ArrowUpRight size={13} />
                        </button>
                      ),
                    )}
                  </div>
                  <ClaimSources
                    key={`${data.source}:${claim.claim_id}`}
                    source={data.source || source}
                    claimId={claim.claim_id}
                  />
                </>
              ) : (
                <>
                  <h2>
                    {entity?.label ||
                      (query
                        ? "Matching relationships"
                        : "Read the connections")}
                  </h2>
                  {entity?.function && <p>{entity.function}</p>}
                  <p className="muted">
                    {related.length}{" "}
                    {related.length === 1 ? "relationship" : "relationships"}
                    {query
                      ? ` matching “${query}” in the loaded graph`
                      : " in view"}
                    . Choose one to inspect the supporting source and context.
                  </p>
                  {related.length === 0 && (
                    <p>
                      No matching relationships in this view. Try another term
                      or claim filter.
                    </p>
                  )}
                  <div className="claim-results">
                    {related.map((e) => (
                      <button
                        className="claim-result"
                        key={keyFor(e)}
                        onClick={() => inspect(e)}
                      >
                        <Status
                          label={human(e.status)}
                          tone={
                            e.status === "disputed" ? "attention" : "neutral"
                          }
                        />
                        <strong>{sentence(e)}</strong>
                        <span>
                          {e.n_sources}{" "}
                          {e.n_sources === 1 ? "source" : "sources"}
                          <ArrowUpRight size={14} />
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
