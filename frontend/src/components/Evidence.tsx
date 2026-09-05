import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { ArrowUpRight, Search, X } from "lucide-react";
import { post, useResource } from "@/lib/api";
import type { Graph, JsonRecord } from "@/lib/types";
import { human, id, number } from "@/lib/utils";
import { Button } from "./ui/button";
import { AnimatedTabs } from "./ui/animated-tabs";
import {
  Disclosure,
  Empty,
  ErrorNotice,
  Loading,
  Modal,
  Status,
} from "./common";

function EntityNode({
  data,
}: NodeProps<Node<{ label: string; degree: number; selected: boolean }>>) {
  return (
    <div className={`entity-node ${data.selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <span className="entity-dot" />
      <strong>{data.label}</strong>
      <small>{data.degree} connections</small>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { entity: EntityNode };
export function Evidence({ project }: { project: string }) {
  const [tab, setTab] = useState("relationships");
  return (
    <div className="evidence-page">
      <header className="page-heading">
        <div>
          <div className="breadcrumb">Research workspace / Evidence</div>
          <h1>Follow the evidence</h1>
          <p>
            Explore literature relationships and review findings before
            accepting them.
          </p>
        </div>
        <AnimatedTabs
          label="Evidence view"
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "relationships", label: "Relationships" },
            { value: "review", label: "Review findings" },
          ]}
        />
      </header>
      {tab === "relationships" ? (
        <Relationships key={project} project={project} />
      ) : (
        <Review key={project} project={project} />
      )}
    </div>
  );
}
function Relationships({ project }: { project: string }) {
  const [source, setSource] = useState(project);
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const graph = useResource<Graph>(
    `/api/kg?limit=120${source ? `&source=${id(source)}` : ""}${status ? `&status=${id(status)}` : ""}`,
    15000,
  );
  const data = graph.data;
  const nodes = useMemo(() => {
    if (!data) return [];
    const sorted = [...data.nodes].sort((a, b) => b.degree - a.degree);
    return sorted.map((n, i) => {
      const ring = Math.floor(Math.sqrt(i));
      const angle = i * 2.399963;
      const radius = ring * 160;
      return {
        id: n.id,
        type: "entity",
        position: {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius * 0.76,
        },
        data: { ...n, selected: n.id === selected },
        style: {
          opacity:
            query && !n.label.toLowerCase().includes(query.toLowerCase())
              ? 0.25
              : 1,
        },
      };
    });
  }, [data, query, selected]);
  const edges =
    data?.edges.map((e, i) => ({
      id: String(i),
      source: e.source,
      target: e.target,
      style: {
        stroke:
          e.source === selected || e.target === selected
            ? "var(--accent)"
            : "var(--edge)",
        strokeWidth: e.source === selected || e.target === selected ? 2 : 0.8,
        opacity:
          selected && e.source !== selected && e.target !== selected
            ? 0.12
            : 0.6,
      },
    })) || [];
  const entity = data?.nodes.find((n) => n.id === selected);
  const related =
    data?.edges.filter((e) => e.source === selected || e.target === selected) ||
    [];
  return (
    <>
      <div className="evidence-toolbar">
        <label className="search-field">
          <Search size={15} />
          <input
            placeholder="Find an entity"
            aria-label="Find an entity"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {!project && (
          <label>
            Collection
            <select
              aria-label="Evidence collection"
              value={source || data?.source || ""}
              onChange={(e) => {
                setSource(e.target.value);
                setSelected("");
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
            onChange={(e) => setStatus(e.target.value)}
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
        <div className="relationships-layout">
          <div className="relationship-canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.1}
              maxZoom={2}
              nodesConnectable={false}
              onNodeClick={(_, n) => setSelected(n.id)}
            >
              <Background gap={24} size={0.6} color="var(--grid)" />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          {entity && (
            <aside className="detail-panel">
              <div className="detail-head">
                <span>Entity connections</span>
                <Button
                  aria-label="Close entity detail"
                  variant="ghost"
                  size="icon"
                  onClick={() => setSelected("")}
                >
                  <X size={16} />
                </Button>
              </div>
              <div className="detail-scroll">
                <h2>{entity.label}</h2>
                {entity.function && <p>{entity.function}</p>}
                <p className="muted">
                  Connections shown are literature claims, not independently
                  confirmed discoveries.
                </p>
                {related.map((e, i) => (
                  <article className="relationship-claim" key={i}>
                    <Status
                      label={human(e.status)}
                      tone={e.status === "disputed" ? "attention" : "neutral"}
                    />
                    <p>
                      <strong>
                        {data.nodes.find((n) => n.id === e.source)?.label}
                      </strong>{" "}
                      {human(e.predicate).toLowerCase()}{" "}
                      <strong>
                        {data.nodes.find((n) => n.id === e.target)?.label}
                      </strong>
                    </p>
                    <small>
                      {e.n_sources} supporting{" "}
                      {e.n_sources === 1 ? "source" : "sources"}
                    </small>
                  </article>
                ))}
              </div>
            </aside>
          )}
        </div>
      )}
    </>
  );
}
function Review({ project }: { project: string }) {
  const queue = useResource<{
    candidates: JsonRecord[];
    promo_decided: Record<string, JsonRecord>;
  }>(`/api/review${project ? `?project=${id(project)}` : ""}`, 10000);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [outcome, setOutcome] = useState("");
  async function decide(card: JsonRecord, decision: string) {
    setBusy(true);
    setError("");
    try {
      await post("/api/review/promotion", {
        project: project || null,
        test_id: card.test_id,
        decision,
        note: notes[card.test_id] || "",
      });
      queue.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const pending = Object.keys(queue.data?.promo_decided || {}).length;
  return (
    <div className="review-page">
      <div className="section-heading">
        <div>
          <h2>Findings awaiting judgment</h2>
          <p className="muted">
            A candidate passed automated checks. Your review determines whether
            it belongs in the accepted evidence.
          </p>
        </div>
        <Button
          disabled={!pending}
          variant="default"
          onClick={() => setConfirm(true)}
        >
          Apply {pending || ""} saved decisions
        </Button>
      </div>
      <ErrorNotice message={queue.error || error} />
      {outcome && (
        <p role="status" className="notice">
          {outcome}
        </p>
      )}
      {queue.loading && <Loading />}
      {queue.data?.candidates.map((c) => (
        <article className="review-card" key={c.test_id}>
          <div className="section-heading">
            <Status
              label={
                queue.data?.promo_decided[c.test_id]
                  ? `Decision saved: ${human(queue.data.promo_decided[c.test_id].decision)}`
                  : "Needs review"
              }
              tone="attention"
            />
            <small>{human(c.method)}</small>
          </div>
          <h2>{c.hypothesis || `${c.subject} and ${c.object}`}</h2>
          <dl className="measurements">
            <div>
              <dt>
                Effect <small>Method-specific units</small>
              </dt>
              <dd>{number(c.effect)}</dd>
            </div>
            <div>
              <dt>Null-test p-value</dt>
              <dd>{number(c.p_null)}</dd>
            </div>
            <div>
              <dt>Novelty assessment</dt>
              <dd>{human(c.novelty_verdict)}</dd>
            </div>
          </dl>
          {c.novelty_detail && (
            <Disclosure title="Novelty evidence">
              <pre>
                {typeof c.novelty_detail === "string"
                  ? c.novelty_detail
                  : JSON.stringify(c.novelty_detail, null, 2)}
              </pre>
            </Disclosure>
          )}
          {c.literature?.quotes?.map((q: string, i: number) => (
            <blockquote key={i}>{q}</blockquote>
          ))}
          <label>
            Review rationale
            <textarea
              rows={3}
              value={
                notes[c.test_id] ??
                queue.data?.promo_decided[c.test_id]?.note ??
                ""
              }
              onChange={(e) =>
                setNotes((n) => ({ ...n, [c.test_id]: e.target.value }))
              }
              placeholder="Explain the evidence supporting your decision."
            />
          </label>
          <div className="review-actions">
            <Button
              disabled={busy || !notes[c.test_id]?.trim()}
              onClick={() => void decide(c, "rejected")}
            >
              Reject finding
            </Button>
            <Button
              variant="default"
              disabled={busy || !notes[c.test_id]?.trim()}
              onClick={() => void decide(c, "validated")}
            >
              Accept finding
            </Button>
          </div>
        </article>
      ))}
      {queue.data?.candidates.length === 0 && (
        <Empty title="No findings awaiting review">
          When an investigation produces a candidate finding, its evidence and
          review controls appear here.
        </Empty>
      )}
      <Modal
        open={confirm}
        onOpenChange={setConfirm}
        title="Apply saved review decisions?"
        description="Accepted findings will be promoted to the master graph. Rejected findings receive your written feedback."
      >
        <ErrorNotice message={error} />
        <Button
          variant="default"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const r = await post<JsonRecord>("/api/review/promotion/apply", {
                project: project || null,
              });
              setOutcome(
                `${r.promoted} promoted, ${r.rejected} rejected, ${r.skipped} skipped.`,
              );
              setConfirm(false);
              queue.refresh();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Applying…" : "Apply decisions"}
        </Button>
      </Modal>
    </div>
  );
}
