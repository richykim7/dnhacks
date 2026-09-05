import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
  type NodeProps,
  type Node,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import {
  ArrowUpRight,
  ChevronRight,
  FlaskConical,
  GitBranch,
  List,
  Pause,
  Play,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useAgent, useResource } from "@/lib/api";
import type {
  Experiment,
  Investigation as InvestigationData,
  JsonRecord,
  RunSummary,
  TreeData,
} from "@/lib/types";
import {
  actionLabel,
  date,
  duration,
  human,
  id,
  number,
  stageLabel,
} from "@/lib/utils";
import { Button } from "./ui/button";
import { AnimatedTabs } from "./ui/animated-tabs";
import { Disclosure, Empty, ErrorNotice, Loading, Status } from "./common";

type AgentData = {
  run: RunSummary;
  title: string;
  count: number;
  selected: boolean;
  onSelect: () => void;
};
function AgentNode({ data }: NodeProps<Node<AgentData>>) {
  const r = data.run;
  const state = r.active
    ? "Working"
    : r.last_action === "done"
      ? "Finished"
      : "No recent activity";
  return (
    <div
      className={`agent-node ${data.selected ? "selected" : ""} ${r.beam?.kept === false ? "closed-branch" : ""}`}
    >
      <Handle type="target" position={Position.Left} />
      <button
        onClick={data.onSelect}
        aria-label={`Inspect ${data.title}`}
        className="agent-button"
      >
        <div className="agent-node-top">
          <span className="agent-kind">
            {r.beam?.adversarial ? (
              <ShieldCheck size={14} />
            ) : (
              <GitBranch size={14} />
            )}{" "}
            {r.depth === 0
              ? "Lead researcher"
              : r.beam?.adversarial
                ? "Challenge branch"
                : `Research branch ${r.run_id.split("~").slice(1).join(".")}`}
          </span>
          <span className={`activity-dot ${r.active ? "live" : ""}`} />
        </div>
        <h3>{data.title}</h3>
        <p>
          {r.active
            ? actionLabel(r.last_action)
            : r.beam?.kept === false
              ? "Not selected to continue"
              : state}
        </p>
        <div className="agent-node-bottom">
          <span>
            <FlaskConical size={13} />
            {data.count} {data.count === 1 ? "experiment" : "experiments"}
          </span>
          <ArrowUpRight size={15} />
        </div>
      </button>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { agent: AgentNode };
function FocusSelection({
  selected,
  count,
}: {
  selected: string | null;
  count: number;
}) {
  const flow = useReactFlow();
  useEffect(() => {
    const duration = window.matchMedia("(prefers-reduced-motion: reduce)")
      .matches
      ? 0
      : 200;
    const timer = setTimeout(() => {
      if (!selected) {
        void flow.fitView({
          padding: 0.18,
          minZoom: window.innerWidth < 700 ? 0.7 : 0.2,
          maxZoom: 1,
          duration,
        });
        return;
      }
      const node = flow.getNode(selected);
      if (node)
        void flow.setCenter(node.position.x + 125, node.position.y + 82, {
          zoom: Math.max(0.75, flow.getZoom()),
          duration,
        });
    }, 220);
    return () => clearTimeout(timer);
  }, [selected, count, flow]);
  return null;
}
export const investigationTitle = (inv: InvestigationData) =>
  (inv as InvestigationData & { goal?: string }).goal ||
  inv.runs.find((r) => !r.parent)?.beam?.angle ||
  "Untitled investigation";

export function Investigation({
  project,
  requestedRun,
  onRun,
  onNew,
}: {
  project: string;
  requestedRun: string;
  onRun: (id: string) => void;
  onNew: () => void;
}) {
  const [includeTests, setIncludeTests] = useState(false);
  const list = useResource<InvestigationData[]>(
    `/api/investigations?all=${includeTests ? 1 : 0}${project ? `&project=${id(project)}` : ""}`,
    5000,
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState("tree");
  const [query, setQuery] = useState("");
  const investigation =
    list.data?.find(
      (t) =>
        t.root === requestedRun ||
        t.runs.some((r) => r.run_id === requestedRun),
    ) || (!requestedRun ? list.data?.[0] : undefined);
  const root = investigation?.root;
  const waitingJobs = useResource<{ jobs: JsonRecord[] }>(
    project && requestedRun && list.data && !investigation
      ? `/api/projects/${id(project)}/jobs`
      : null,
    2000,
  );
  const waitingJob = waitingJobs.data?.jobs.find(
    (j) => j.run_id === requestedRun,
  );
  const tree = useResource<TreeData>(
    root ? `/api/tree/${id(root)}` : null,
    5000,
  );
  const events = useResource<JsonRecord>(
    root ? `/api/events/${id(root)}` : null,
    5000,
  );
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    setSelected(null);
    setCursor(null);
    setPlaying(false);
  }, [root, project]);
  const allEvents: JsonRecord[] = events.data?.events || [];
  const max = allEvents.length;
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () =>
        setCursor((n) => {
          const next = Math.min((n ?? 0) + 1, max);
          if (next >= max) setPlaying(false);
          return next;
        }),
      500,
    );
    return () => clearInterval(timer);
  }, [playing, max]);
  const historic = cursor !== null;
  const visibleEvents = historic ? allEvents.slice(0, cursor) : allEvents;
  const visibleRuns = useMemo(() => {
    if (!investigation) return [];
    if (!historic) return investigation.runs;
    const known = new Set([
      root,
      ...visibleEvents.map((e) => e.run_id),
      ...visibleEvents
        .filter((e) => e.type === "fork")
        .flatMap((e) => (e.children || []).map((c: JsonRecord) => c.run_id)),
    ]);
    return investigation.runs
      .filter((r) => known.has(r.run_id))
      .map((r) => {
        const last = visibleEvents
          .filter((e) => e.run_id === r.run_id && e.type === "step")
          .at(-1);
        return {
          ...r,
          active: false,
          last_action: last?.action || "",
          beam: undefined,
        };
      });
  }, [investigation, historic, visibleEvents, root]);
  useEffect(() => {
    if (selected && !visibleRuns.some((r) => r.run_id === selected))
      setSelected(null);
  }, [selected, visibleRuns]);
  const nodes = useMemo(() => {
    const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: "LR",
      nodesep: 40,
      ranksep: 100,
      marginx: 50,
      marginy: 60,
    });
    visibleRuns.forEach((r) =>
      g.setNode(r.run_id, { width: 250, height: 164 }),
    );
    visibleRuns.forEach((r) => {
      if (r.parent && visibleRuns.some((p) => p.run_id === r.parent))
        g.setEdge(r.parent, r.run_id);
    });
    dagre.layout(g);
    return visibleRuns.map((r) => ({
      id: r.run_id,
      type: "agent",
      position: { x: g.node(r.run_id).x - 125, y: g.node(r.run_id).y - 82 },
      data: {
        run: r,
        title:
          r.beam?.angle ||
          (r.depth === 0
            ? investigationTitle(investigation!)
            : `Branch ${r.run_id.split("~").slice(1).join(".")}`),
        count: historic
          ? visibleEvents
              .filter((e) => e.run_id === r.run_id && e.type === "experiment")
              .reduce((total, e) => total + (e.n ?? 1), 0)
          : tree.data?.nodes.filter(
              (e) => e.run_id === r.run_id && e.kind === "experiment",
            ).length || 0,
        selected: r.run_id === selected,
        onSelect: () => setSelected(r.run_id),
      },
      draggable: false,
    }));
  }, [
    visibleRuns,
    tree.data,
    selected,
    investigation,
    historic,
    visibleEvents,
  ]);
  const edges = visibleRuns
    .filter((r) => r.parent && visibleRuns.some((p) => p.run_id === r.parent))
    .map((r) => ({
      id: `${r.parent}-${r.run_id}`,
      source: r.parent!,
      target: r.run_id,
      type: "default",
      className: r.run_id === selected ? "selected-edge" : "",
      style: {
        stroke: r.run_id === selected ? "var(--accent)" : "var(--edge)",
        strokeWidth: r.run_id === selected ? 2 : 1.3,
        strokeDasharray: r.beam?.kept === false ? "5 5" : undefined,
      },
    }));
  const filtered =
    list.data?.filter((t) =>
      `${investigationTitle(t)} ${t.root}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    ) || [];
  return (
    <div className="investigation-layout">
      <aside className="run-rail">
        <div className="rail-title">
          <h2>Investigations</h2>
          <Button
            size="icon"
            variant="ghost"
            aria-label="New investigation"
            onClick={onNew}
          >
            <span className="plus">+</span>
          </Button>
        </div>
        <label className="search-field">
          <Search size={15} />
          <input
            aria-label="Find investigation"
            placeholder="Find an investigation"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <div className="run-list">
          {list.loading && <Loading label="Loading investigations" />}
          <ErrorNotice message={list.error} retry={list.refresh} />
          {filtered.map((t, index) => (
            <button
              className={`run-row ${t.root === root ? "selected" : ""}`}
              key={t.root}
              onClick={() => onRun(t.root)}
            >
              <span className="run-row-heading">
                <span className={`activity-dot ${t.active ? "live" : ""}`} />
                {t.active
                  ? "In progress"
                  : t.last_action === "done"
                    ? "Recorded"
                    : "Paused"}
              </span>
              <strong>
                {investigationTitle(t) === "Untitled investigation"
                  ? `Investigation ${list.data!.length - index}`
                  : investigationTitle(t)}
              </strong>
              <span>{date(t.updated_at)}</span>
              <span className="run-row-foot">
                {t.n_runs} researchers <ChevronRight size={13} />
              </span>
            </button>
          ))}
          {!list.loading && !filtered.length && (
            <p className="rail-empty">
              {query
                ? "No matching investigations."
                : "Your investigations will appear here."}
            </p>
          )}
        </div>
        <label className="rail-option">
          <input
            type="checkbox"
            checked={includeTests}
            onChange={(e) => setIncludeTests(e.target.checked)}
          />
          Include test runs
        </label>
      </aside>
      <section className="investigation-main">
        {!investigation ? (
          list.loading || (project && requestedRun && waitingJobs.loading) ? (
            <Loading />
          ) : waitingJob ? (
            <Empty
              title={
                waitingJob.status === "running"
                  ? "Your investigation is starting"
                  : "The investigation stopped before recording activity"
              }
            >
              {waitingJob.status === "running"
                ? "The research process has started. Its first recorded step will open the tree automatically."
                : waitingJob.error ||
                  "Open Builds & runs in the Library to inspect the process log."}
            </Empty>
          ) : (
            <Empty
              title={
                requestedRun
                  ? "Investigation not in this project"
                  : "Start with a research question"
              }
              action={
                <Button variant="default" onClick={onNew}>
                  Start an investigation <ArrowUpRight size={15} />
                </Button>
              }
            >
              {requestedRun
                ? "Choose another investigation or switch to All projects to open this link."
                : "Build a literature collection, ask a research question, and follow each branch of the investigation as it unfolds."}
            </Empty>
          )
        ) : (
          <>
            <header className="canvas-header">
              <div>
                <div className="breadcrumb">
                  Research workspace <ChevronRight size={12} /> Investigation
                </div>
                <h1>{investigationTitle(investigation)}</h1>
              </div>
              <Status
                label={
                  historic
                    ? "History playback"
                    : investigation.active
                      ? "Receiving activity"
                      : "Recorded investigation"
                }
                tone={investigation.active && !historic ? "live" : "neutral"}
              />
            </header>
            <div className="canvas-toolbar">
              <AnimatedTabs
                label="Investigation view"
                value={view}
                onChange={setView}
                tabs={[
                  { value: "tree", label: "Search tree" },
                  { value: "activity", label: "Activity" },
                  { value: "experiments", label: "Experiments" },
                ]}
              />
              <div className="toolbar-note">
                {visibleRuns.length} researchers<span>·</span>
                {historic
                  ? visibleEvents
                      .filter((e) => e.type === "experiment")
                      .reduce((total, e) => total + (e.n ?? 1), 0)
                  : (tree.data?.counts.experiments ?? "—")}{" "}
                experiments
              </div>
            </div>
            <ErrorNotice message={tree.error || events.error} />
            {tree.data?.db_unreadable && (
              <ErrorNotice
                message="Experiment records are temporarily unavailable. Agent activity remains available."
                retry={tree.refresh}
              />
            )}
            {tree.data &&
              (tree.data.orphans.length > 0 ||
                tree.data.unverified_submissions.length > 0) && (
                <div className="notice">
                  {tree.data.orphans.length > 0 &&
                    `${tree.data.orphans.length} recorded links could not be resolved. `}
                  {tree.data.unverified_submissions.length > 0 &&
                    `${tree.data.unverified_submissions.length} submissions have no verification result yet.`}
                </div>
              )}
            <div className="canvas-and-detail">
              <div className="research-stage">
                {view === "tree" && (
                  <>
                    <div className="canvas-caption">
                      <GitBranch size={15} />
                      <span>
                        Follow the research
                        <br />
                        <small>Select a researcher to inspect its work</small>
                      </span>
                    </div>
                    <ReactFlowProvider>
                      <ReactFlow
                        key={root}
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypes}
                        fitView
                        fitViewOptions={{ padding: 0.18, maxZoom: 1 }}
                        minZoom={0.15}
                        maxZoom={1.5}
                        nodesDraggable={false}
                        nodesConnectable={false}
                        onNodeClick={(_, n) => setSelected(n.id)}
                        colorMode="system"
                      >
                        <Background
                          variant={BackgroundVariant.Dots}
                          gap={22}
                          size={0.7}
                          color="var(--grid)"
                        />
                        <Controls showInteractive={false} />
                        <FocusSelection
                          selected={selected}
                          count={nodes.length}
                        />
                      </ReactFlow>
                    </ReactFlowProvider>
                  </>
                )}
                {view === "activity" && (
                  <div className="activity-page">
                    <h2>Investigation activity</h2>
                    <p className="muted">
                      Recorded actions across every research branch.
                    </p>
                    {[...visibleEvents]
                      .reverse()
                      .slice(0, 300)
                      .map((e, i) => (
                        <button
                          className="event-row"
                          key={e.id || `${e.run_id}-${i}`}
                          onClick={() => setSelected(e.run_id)}
                        >
                          <span className="event-time">{date(e.t)}</span>
                          <span>
                            <strong>{actionLabel(e.action || e.type)}</strong>
                            <small>{e.title || e.run_id}</small>
                          </span>
                          <ArrowUpRight size={14} />
                        </button>
                      ))}
                    {!visibleEvents.length && (
                      <p>No activity recorded at this point.</p>
                    )}
                  </div>
                )}
                {view === "experiments" && (
                  <div className="activity-page">
                    <h2>Experiments</h2>
                    {historic ? (
                      <p>
                        Return to the latest state to inspect full experiment
                        results.
                      </p>
                    ) : (
                      tree.data?.nodes
                        .filter((n) => n.kind === "experiment")
                        .map((n) => (
                          <button
                            className="experiment-row"
                            key={n.entry_id}
                            onClick={() => setSelected(n.run_id)}
                          >
                            <FlaskConical size={17} />
                            <span>
                              <strong>{n.title}</strong>
                              <small>
                                {n.method
                                  ? human(n.method)
                                  : "Method not recorded"}
                              </small>
                            </span>
                            <Status label={stageLabel(n.stage)} />
                            <ArrowUpRight size={14} />
                          </button>
                        ))
                    )}
                    {!historic &&
                      !tree.data?.nodes.some(
                        (n) => n.kind === "experiment",
                      ) && (
                        <Empty title="No experiments recorded yet">
                          Experiments appear here when a researcher records an
                          analysis.
                        </Empty>
                      )}
                  </div>
                )}
              </div>
              <AnimatePresence mode="wait">
                {selected && (
                  <motion.aside
                    className="detail-panel"
                    initial={{ opacity: 0, x: 14 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 14 }}
                    transition={{ duration: 0.18 }}
                    key={selected}
                  >
                    <AgentDetail
                      runId={selected}
                      summary={investigation.runs.find(
                        (r) => r.run_id === selected,
                      )}
                      experiments={
                        tree.data?.nodes.filter((n) => n.run_id === selected) ||
                        []
                      }
                      onClose={() => setSelected(null)}
                      historic={historic}
                      events={visibleEvents}
                    />
                  </motion.aside>
                )}
              </AnimatePresence>
            </div>
            <footer className="playback">
              <Button
                size="icon"
                variant="ghost"
                aria-label={
                  playing ? "Pause playback" : "Play recorded activity"
                }
                disabled={!max}
                onClick={() => {
                  if (playing) setPlaying(false);
                  else {
                    setCursor(cursor === null || cursor >= max ? 0 : cursor);
                    setPlaying(true);
                  }
                }}
              >
                {playing ? <Pause size={15} /> : <Play size={15} />}
              </Button>
              <span>{historic ? "Playback" : "Latest"}</span>
              <input
                type="range"
                aria-label="Activity playback position"
                min={0}
                max={max || 1}
                value={cursor ?? max}
                disabled={!max}
                onChange={(e) => {
                  setPlaying(false);
                  setCursor(Number(e.target.value));
                }}
              />
              <span className="mono">
                {cursor ?? max} / {max}
              </span>
              <Button
                size="sm"
                variant={historic ? "secondary" : "ghost"}
                onClick={() => {
                  setCursor(null);
                  setPlaying(false);
                }}
              >
                Latest state
              </Button>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}

function AgentDetail({
  runId,
  summary,
  experiments,
  onClose,
  historic,
  events,
}: {
  runId: string;
  summary?: RunSummary;
  experiments: Experiment[];
  onClose: () => void;
  historic: boolean;
  events: JsonRecord[];
}) {
  const { run, error, connection } = useAgent(historic ? null : runId);
  const [tab, setTab] = useState("activity");
  const [follow, setFollow] = useState(true);
  const steps = historic
    ? events.filter((e) => e.run_id === runId && e.type === "step")
    : run?.steps || [];
  const sorted = follow ? [...steps].reverse() : steps;
  return (
    <>
      <div className="detail-head">
        <span>
          <GitBranch size={15} />
          {summary?.depth === 0 ? "Lead researcher" : "Research branch"}
        </span>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Close researcher detail"
          onClick={onClose}
        >
          <X size={17} />
        </Button>
      </div>
      <div className="detail-intro">
        <Status
          label={historic ? "Recorded at cursor" : connection}
          tone={connection === "Connected" && !historic ? "live" : "neutral"}
        />
        <h2>
          {summary?.beam?.angle ||
            (summary?.depth === 0 ? "Lead investigation" : "Research branch")}
        </h2>
        {summary?.beam?.reason && !historic && <p>{summary.beam.reason}</p>}
        <Disclosure title="Researcher reference">
          <code>{runId}</code>
          {summary?.beam?.rank != null && (
            <p>Parent’s ranking: {summary.beam.rank}</p>
          )}
        </Disclosure>
      </div>
      <AnimatedTabs
        label="Researcher detail"
        value={tab}
        onChange={setTab}
        tabs={[
          { value: "activity", label: "Activity" },
          { value: "experiments", label: "Experiments" },
        ]}
      />
      <div className="detail-scroll">
        <ErrorNotice message={error} />
        {!historic && !run && !error && <Loading label="Opening researcher" />}
        {tab === "activity" && (
          <>
            <div className="section-heading">
              <h3>{historic ? "Recorded activity" : "Research log"}</h3>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setFollow((v) => !v)}
              >
                {follow ? "Newest first" : "Oldest first"} <List size={13} />
              </Button>
            </div>
            {sorted.slice(0, 150).map((s, i) => (
              <article
                className="activity-entry"
                key={`${s.step}-${s.ts}-${i}`}
              >
                <div className="entry-meta">
                  <span className="activity-dot" />
                  {actionLabel(s.action)}
                  <time>{duration(s.dt_s)}</time>
                </div>
                {s.reasoning && <p>{s.reasoning}</p>}
                {s.observation && (
                  <Disclosure title="Observation">
                    <pre>
                      {typeof s.observation === "string"
                        ? s.observation
                        : JSON.stringify(s.observation, null, 2)}
                    </pre>
                  </Disclosure>
                )}
                {s.args && Object.keys(s.args).length > 0 && (
                  <Disclosure title="Inputs">
                    <pre>{JSON.stringify(s.args, null, 2)}</pre>
                  </Disclosure>
                )}
              </article>
            ))}
            {steps.length === 0 && (
              <p className="muted">
                No recorded steps yet. Activity will appear when the researcher
                writes an update.
              </p>
            )}
          </>
        )}
        {tab === "experiments" &&
          (historic ? (
            <p className="muted">
              Return to the latest state to inspect complete results. Later
              results are hidden during playback.
            </p>
          ) : experiments.length ? (
            experiments.map((n) => (
              <ExperimentDetail key={n.entry_id} experiment={n} />
            ))
          ) : (
            <p className="muted">
              This researcher has not recorded an experiment yet.
            </p>
          ))}
      </div>
    </>
  );
}

export function ExperimentDetail({
  experiment: n,
}: {
  experiment: Experiment;
}) {
  return (
    <article className="experiment-detail">
      <Status
        label={stageLabel(n.verdict || n.stage)}
        tone={
          n.stage === "candidate"
            ? "attention"
            : n.stage === "killed"
              ? "negative"
              : "neutral"
        }
      />
      <h3>{n.title}</h3>
      {n.body && <p>{n.body}</p>}
      {n.kill_reason && <p className="notice">{n.kill_reason}</p>}
      {n.verdict_note && <p>{n.verdict_note}</p>}
      <dl className="measurements">
        <div>
          <dt>Analysis</dt>
          <dd>{human(n.method)}</dd>
        </div>
        {n.effect != null && (
          <div>
            <dt>
              Effect <small>Method-specific units</small>
            </dt>
            <dd>{number(n.effect)}</dd>
          </div>
        )}
        {n.p_null != null && (
          <div>
            <dt>Null-test p-value</dt>
            <dd>{number(n.p_null)}</dd>
          </div>
        )}
        {n.n_units != null && (
          <div>
            <dt>Independent samples</dt>
            <dd>{number(n.n_units)}</dd>
          </div>
        )}
        {n.robust != null && (
          <div>
            <dt>Robustness check</dt>
            <dd>{n.robust ? "Passed" : "Did not pass"}</dd>
          </div>
        )}
      </dl>
      {n.failed && (
        <p className="notice">
          {n.raised
            ? "The analysis raised an error."
            : "No measurable result was recorded."}
        </p>
      )}
      {n.retry_of != null && (
        <p className="muted">Retry of experiment {n.retry_of}</p>
      )}
      {n.code && (
        <Disclosure title="Analysis code">
          <pre>{n.code}</pre>
        </Disclosure>
      )}
      {n.result && (
        <Disclosure title="Full result">
          <pre>{JSON.stringify(n.result, null, 2)}</pre>
        </Disclosure>
      )}
      {n.failed && n.output && (
        <Disclosure title="Recorded output">
          <pre>{n.output}</pre>
        </Disclosure>
      )}
      {n.provenance && (
        <Disclosure title="Data and provenance">
          <pre>{JSON.stringify(n.provenance, null, 2)}</pre>
        </Disclosure>
      )}
    </article>
  );
}
