import { useEffect, useMemo, useRef, useState } from "react";
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
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  Play,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import {
  AnimatePresence,
  LayoutGroup,
  motion,
  useReducedMotion,
} from "motion/react";
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
import {
  emptyRuntime,
  reduceRuntime,
  runtimeCandidates,
  runtimeRunSummary,
  useRuntime,
} from "@/lib/runtime";
import { RuntimeDetail } from "./RuntimeDetail";
import "@/investigation.css";

const NODE_WIDTH = 286;
const NODE_HEIGHT = 190;
type AgentData = {
  run: RunSummary;
  title: string;
  count: number;
  candidates: number;
  activity: boolean;
  state: string;
  elapsed: string;
  selected: boolean;
  onSelect: () => void;
  onCandidate: () => void;
};
function AgentNode({ data }: NodeProps<Node<AgentData>>) {
  const r = data.run;
  const reducedMotion = useReducedMotion();
  return (
    <motion.div
      layoutId={`researcher-${r.run_id}`}
      transition={
        reducedMotion
          ? { duration: 0 }
          : { type: "spring", stiffness: 320, damping: 34 }
      }
      style={{ borderRadius: 12 }}
      className={`agent-node ${data.selected ? "selected" : ""} ${data.activity ? "is-working" : ""} ${data.candidates ? "has-candidates" : ""} ${r.beam?.kept === false ? "closed-branch" : ""}`}
    >
      <Handle type="target" position={Position.Top} />
      <button
        onClick={data.onSelect}
        aria-label={`${data.selected ? "Collapse" : "Inspect"} ${data.title}`}
        aria-expanded={data.selected}
        className="agent-button nodrag"
      >
        <div className="agent-node-top">
          <span className="agent-kind">
            {r.beam?.adversarial ? (
              <ShieldCheck size={14} />
            ) : (
              <GitBranch size={14} />
            )}
            {r.depth === 0
              ? "Lead researcher"
              : r.beam?.adversarial
                ? "Challenge branch"
                : `Research branch ${r.run_id.split("~").slice(1).join(".")}`}
          </span>
          <span className={`activity-dot ${data.activity ? "live" : ""}`} />
        </div>
        <h3>{data.title}</h3>
        <p>
          {data.state}
          {data.elapsed && ` · ${data.elapsed}`}
        </p>
      </button>
      <div className="agent-node-bottom">
        <span>
          <FlaskConical size={13} />
          {data.count} {data.count === 1 ? "experiment" : "experiments"}
        </span>
        {data.candidates > 0 && (
          <button
            type="button"
            className="candidate-badge nodrag"
            onClick={data.onCandidate}
            title="Open automated candidates; not accepted discoveries"
          >
            <Sparkles size={13} />
            {data.candidates}{" "}
            {data.candidates === 1 ? "candidate" : "candidates"}
          </button>
        )}
        <ChevronRight size={15} className="node-expand-chevron" />
      </div>
      <Handle type="source" position={Position.Bottom} />
    </motion.div>
  );
}
const nodeTypes = { agent: AgentNode };
function CanvasViewport({ manual }: { manual: { current: boolean } }) {
  const flow = useReactFlow();
  const initialized = flow.viewportInitialized;
  useEffect(() => {
    if (!initialized) return;
    const canvas = document.querySelector(".investigation-layout .react-flow");
    const duration = window.matchMedia("(prefers-reduced-motion: reduce)")
      .matches
      ? 0
      : 300;
    const fit = () => {
      if (!manual.current)
        void flow.fitView({ padding: 0.18, maxZoom: 1, duration });
    };
    let timer = window.setTimeout(fit, 340);
    let width = canvas?.clientWidth,
      height = canvas?.clientHeight;
    const observer = new ResizeObserver(() => {
      if (
        !canvas ||
        (canvas.clientWidth === width && canvas.clientHeight === height)
      )
        return;
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      window.clearTimeout(timer);
      timer = window.setTimeout(fit, 180);
    });
    if (canvas) observer.observe(canvas);
    return () => {
      window.clearTimeout(timer);
      observer.disconnect();
    };
  }, [initialized, flow, manual]);
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
  const reducedMotion = useReducedMotion();
  const closingRun = useRef<string | null>(null);
  const pendingView = useRef<string | null>(null);
  const manualViewport = useRef(false);
  const workspace = useRef<HTMLElement>(null);
  const [railCollapsed, setRailCollapsed] = useState(
    () => window.innerWidth < 900,
  );
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() / 1000), 10000);
    return () => clearInterval(timer);
  }, []);
  const [includeTests, setIncludeTests] = useState(false);
  const list = useResource<InvestigationData[]>(
    `/api/investigations?all=${includeTests ? 1 : 0}${project ? `&project=${id(project)}` : ""}`,
    5000,
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(
    null,
  );
  const selectAgent = (run: string) => {
    setSelectedExperiment(null);
    setSelected((current) => (current === run ? null : run));
    setView("tree");
  };
  const [view, setView] = useState("tree");
  const changeView = (next: string) => {
    if (selected) {
      closingRun.current = selected;
      pendingView.current = next;
      setSelected(null);
    } else setView(next);
  };
  const [query, setQuery] = useState("");
  const investigation =
    list.data?.find(
      (t) =>
        t.root === requestedRun ||
        t.runs.some((r) => r.run_id === requestedRun),
    ) || (!requestedRun ? list.data?.[0] : undefined);
  const root = investigation?.root;
  const runtime = useRuntime(
    investigation?.runtime && root ? root : null,
    project,
  );
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
    root && !investigation?.runtime ? `/api/tree/${id(root)}` : null,
    5000,
  );
  const events = useResource<JsonRecord>(
    root && !investigation?.runtime ? `/api/events/${id(root)}` : null,
    5000,
  );
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    setSelected(null);
    manualViewport.current = false;
    pendingView.current = null;
    setSelectedExperiment(null);
    setCursor(null);
    setPlaying(false);
  }, [root, project]);
  const allEvents: JsonRecord[] = investigation?.runtime
    ? runtime.events.map((e) => ({
        ...e,
        id: e.event_id,
        type: e.kind,
        action: e.payload.action || e.kind.replaceAll(".", " "),
        title: e.payload.intent || e.payload.title || e.payload.label || "",
        t: e.recorded_at,
      }))
    : events.data?.events || [];
  const max = allEvents.length;
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () =>
        setCursor((n) => {
          const next = Math.min((n ?? 0) + 1, max);
          if (next >= max) setPlaying(false);
          return next;
        }),
      500 / playbackSpeed,
    );
    return () => clearInterval(timer);
  }, [playing, max, playbackSpeed]);
  const historic = cursor !== null;
  const visibleEvents = historic ? allEvents.slice(0, cursor) : allEvents;
  const runtimeState = useMemo(
    () =>
      (historic ? runtime.events.slice(0, cursor) : runtime.events).reduce(
        reduceRuntime,
        emptyRuntime(),
      ),
    [runtime.events, historic, cursor],
  );
  const visibleRuns = useMemo(() => {
    if (!investigation) return [];
    if (investigation.runtime)
      return Object.values(runtimeState.runs).map(
        (r) =>
          ({
            run_id: r.run_id,
            root: root!,
            parent: r.parent_run_id || null,
            depth: r.run_id.split("~").length - 1,
            steps: r.history.length,
            active: !historic && ["running", "reporting"].includes(r.lifecycle),
            last_action: r.activity?.action || "",
            updated_at: r.updated_at,
            runtime: true,
            lifecycle: r.lifecycle,
            objective: r.branch_objective,
            beam: r.decision?.decision
              ? {
                  reason: r.decision.decision.reason,
                  kept:
                    r.decision.decision.action === "prune" ? false : undefined,
                }
              : r.decision,
          }) as RunSummary,
      );
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
  }, [investigation, historic, visibleEvents, root, runtimeState]);
  useEffect(() => {
    if (selected && !visibleRuns.some((r) => r.run_id === selected))
      setSelected(null);
  }, [selected, visibleRuns]);
  const closeResearcher = () => {
    closingRun.current = selected;
    setSelected(null);
  };
  useEffect(() => {
    if (!selected) return;
    const frame = requestAnimationFrame(() =>
      workspace.current
        ?.querySelector<HTMLButtonElement>("[data-workspace-close]")
        ?.focus({ preventScroll: true }),
    );
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closingRun.current = selected;
        setSelected(null);
      }
    };
    window.addEventListener("keydown", close);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("keydown", close);
    };
  }, [selected]);
  // Expansion never changes tree geometry or the user’s viewport. Only topology lays out nodes.
  const topology = JSON.stringify(visibleRuns.map((r) => [r.run_id, r.parent]));
  const positions = useMemo(() => {
    const runs: [string, string | null][] = JSON.parse(topology);
    const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: "TB",
      nodesep: 36,
      ranksep: 86,
      marginx: 36,
      marginy: 42,
    });
    runs.forEach(([run]) =>
      g.setNode(run, {
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      }),
    );
    runs.forEach(([run, parent]) => {
      if (parent && g.hasNode(parent)) g.setEdge(parent, run);
    });
    dagre.layout(g);
    return Object.fromEntries(
      runs.map(([run]) => [
        run,
        {
          x: g.node(run).x - NODE_WIDTH / 2,
          y: g.node(run).y - NODE_HEIGHT / 2,
        },
      ]),
    );
  }, [topology]);
  const summaries = Object.fromEntries(
    visibleRuns.map((r) => [
      r.run_id,
      runtimeRunSummary(
        runtimeState.runs[r.run_id],
        historic ? visibleEvents.at(-1)?.t || 0 : now,
        historic,
      ),
    ]),
  );
  const candidates = Object.values(runtimeState.runs).flatMap((r) =>
    runtimeCandidates(r).map((experiment) => ({ run: r, experiment })),
  );
  const openCandidate = (runId: string, experimentId: string) => {
    setView("tree");
    setSelected(runId);
    setSelectedExperiment(experimentId);
  };
  const nodes = useMemo(() => {
    return visibleRuns.map((r) => ({
      id: r.run_id,
      type: "agent",
      position: positions[r.run_id],
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
      data: {
        run: r,
        title:
          r.objective ||
          r.beam?.angle ||
          (r.depth === 0
            ? investigationTitle(investigation!)
            : `Branch ${r.run_id.split("~").slice(1).join(".")}`),
        count: investigation?.runtime
          ? Object.keys(runtimeState.runs[r.run_id]?.experiments || {}).length
          : historic
            ? visibleEvents
                .filter((e) => e.run_id === r.run_id && e.type === "experiment")
                .reduce((total, e) => total + (e.n ?? 1), 0)
            : tree.data?.nodes.filter(
                (e) => e.run_id === r.run_id && e.kind === "experiment",
              ).length || 0,
        candidates: summaries[r.run_id].candidateCount,
        onCandidate: () => {
          const choices = runtimeCandidates(runtimeState.runs[r.run_id]);
          const first =
            choices.find(
              (e) => !["validated", "rejected"].includes(e.human_review),
            ) || choices[0];
          if (first) openCandidate(r.run_id, first.experiment_id);
        },
        activity: investigation?.runtime
          ? summaries[r.run_id].freshActivity
          : !historic && r.active && now - r.updated_at < 90,
        state: investigation?.runtime
          ? summaries[r.run_id].status === "stale"
            ? "Waiting for heartbeat"
            : human(summaries[r.run_id].status)
          : human(r.lifecycle || r.last_action || "Idle"),
        elapsed:
          summaries[r.run_id].elapsedSeconds != null
            ? duration(summaries[r.run_id].elapsedSeconds!)
            : "",
        selected: r.run_id === selected,
        onSelect: () => selectAgent(r.run_id),
      },
      draggable: false,
    }));
  }, [
    visibleRuns,
    positions,
    now,
    project,
    selectedExperiment,
    runtime.connection,
    tree.data,
    selected,
    investigation,
    historic,
    visibleEvents,
    runtimeState,
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
  const selectedTitle =
    nodes.find((node) => node.id === selected)?.data.title || "Researcher";
  const filtered =
    list.data?.filter((t) =>
      `${investigationTitle(t)} ${t.root}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    ) || [];
  return (
    <div
      className={`investigation-layout investigation-redesign ${railCollapsed ? "rail-collapsed" : ""}`}
    >
      <aside className="run-rail" aria-label="Investigation navigation">
        <Button
          className="rail-collapse"
          size="icon"
          variant="ghost"
          aria-label={
            railCollapsed
              ? "Expand investigation list"
              : "Collapse investigation list"
          }
          aria-expanded={!railCollapsed}
          aria-controls="investigation-navigation"
          onClick={() => setRailCollapsed((value) => !value)}
        >
          {railCollapsed ? (
            <PanelLeftOpen size={17} />
          ) : (
            <PanelLeftClose size={17} />
          )}
        </Button>
        <div
          id="investigation-navigation"
          className="run-rail-content"
          hidden={railCollapsed}
        >
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
                  <span
                    className={`activity-dot ${t.active && now - t.updated_at < 20 ? "live" : ""}`}
                  />
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
                  {historic && t.root === root ? visibleRuns.length : t.n_runs}{" "}
                  researchers <ChevronRight size={13} />
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
        </div>
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
                      ? Object.values(summaries).some((s) => s.freshActivity)
                        ? "Live research"
                        : "Waiting for activity"
                      : "Recorded investigation"
                }
                tone={
                  Object.values(summaries).some((s) => s.freshActivity) &&
                  !historic
                    ? "live"
                    : "neutral"
                }
              />
            </header>
            <ErrorNotice message={runtime.error} />
            {!investigation.runtime && (
              <p className="legacy-notice">
                Legacy history · lifecycle and full replay were not recorded.
              </p>
            )}
            <div className="canvas-toolbar">
              <AnimatedTabs
                label="Investigation view"
                value={view}
                onChange={changeView}
                tabs={[
                  { value: "tree", label: "Search tree" },
                  { value: "experiments", label: "Experiments" },
                  ...(investigation.runtime
                    ? [{ value: "candidates", label: "Candidates" }]
                    : []),
                  { value: "activity", label: "Diagnostics" },
                ]}
              />
              <div className="toolbar-note">
                {visibleRuns.length} researchers<span>·</span>
                {visibleRuns.length
                  ? Math.max(...visibleRuns.map((run) => run.depth)) + 1
                  : 0}{" "}
                generations<span>·</span>
                {investigation.runtime
                  ? Object.values(runtimeState.runs).reduce(
                      (sum, r) => sum + Object.keys(r.experiments).length,
                      0,
                    )
                  : historic
                    ? visibleEvents
                        .filter((e) => e.type === "experiment")
                        .reduce((total, e) => total + (e.n ?? 1), 0)
                    : (tree.data?.counts.experiments ?? "—")}{" "}
                experiments
                {investigation.runtime && (
                  <button
                    className="candidate-badge summary-candidates"
                    onClick={() => changeView("candidates")}
                    title="Review automated candidates separately from accepted discoveries"
                  >
                    <Sparkles size={13} />
                    {candidates.length} candidates
                  </button>
                )}
                {Object.values(summaries).some((s) => s.acceptedCount > 0) && (
                  <span>
                    {Object.values(summaries).reduce(
                      (sum, s) => sum + s.acceptedCount,
                      0,
                    )}{" "}
                    accepted
                  </span>
                )}
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
            <LayoutGroup id={`investigation-${root}`}>
              <div className="canvas-and-detail">
                <div className="research-stage">
                  <div
                    className={`tree-layer ${view !== "tree" ? "tree-layer-hidden" : ""}`}
                    inert={Boolean(selected) || view !== "tree"}
                    aria-hidden={Boolean(selected) || view !== "tree"}
                  >
                    <div className="canvas-caption">
                      <GitBranch size={15} />
                      <span>
                        Follow the research
                        <br />
                        <small>Select a researcher to inspect its work</small>
                      </span>
                    </div>
                    <ReactFlowProvider key={root}>
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
                        autoPanOnNodeFocus={false}
                        onMoveStart={(event) => {
                          if (event) manualViewport.current = true;
                        }}
                        colorMode="system"
                      >
                        <Background
                          variant={BackgroundVariant.Dots}
                          gap={22}
                          size={0.7}
                          color="var(--grid)"
                        />
                        <Controls showInteractive={false} />
                        <CanvasViewport manual={manualViewport} />
                      </ReactFlow>
                    </ReactFlowProvider>
                  </div>
                  {view === "candidates" && (
                    <div className="activity-page candidate-queue">
                      <h2>Candidate review</h2>
                      <p className="muted">
                        Automated candidate emissions await human review.
                        Accepting a candidate records a review decision; it does
                        not confirm a discovery.
                      </p>
                      {historic && (
                        <p className="muted">
                          Candidate state at this playback position. Return to
                          Latest state to review.
                        </p>
                      )}
                      {candidates.map(({ run, experiment }) => (
                        <button
                          className="experiment-row"
                          key={`${run.run_id}:${experiment.experiment_id}`}
                          onClick={() =>
                            openCandidate(run.run_id, experiment.experiment_id)
                          }
                        >
                          <Sparkles size={17} />
                          <span>
                            <strong>
                              {experiment.title || "Candidate experiment"}
                            </strong>
                            <small>
                              {run.branch_objective ||
                                (run.parent_run_id
                                  ? "Research branch"
                                  : "Lead researcher")}{" "}
                              · {experiment.verification || "Candidate emitted"}
                            </small>
                          </span>
                          <Status
                            label={
                              experiment.human_review === "validated"
                                ? "Accepted"
                                : experiment.human_review === "rejected"
                                  ? "Rejected"
                                  : "Needs review"
                            }
                          />
                          <ArrowUpRight size={14} />
                        </button>
                      ))}
                      {!candidates.length && (
                        <Empty title="No candidates at this point">
                          Candidate emissions appear here and on the researcher
                          that produced them.
                        </Empty>
                      )}
                    </div>
                  )}
                  {view === "activity" && (
                    <div className="activity-page">
                      <h2>Advanced event diagnostics</h2>
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
                            onClick={() => selectAgent(e.run_id)}
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
                      {investigation.runtime ? (
                        Object.values(runtimeState.runs).flatMap((r) =>
                          Object.values(r.experiments).map((exp: any) => (
                            <button
                              className="experiment-row"
                              key={exp.experiment_id}
                              data-scene-run={r.run_id}
                              data-scene-experiment={exp.experiment_id}
                              onClick={() => {
                                setView("tree");
                                setSelected(r.run_id);
                                setSelectedExperiment(exp.experiment_id);
                              }}
                            >
                              <FlaskConical size={17} />
                              <span>
                                <strong>{exp.title || "Experiment"}</strong>
                                <small>{human(exp.method)}</small>
                              </span>
                              <Status label={human(exp.status)} />
                            </button>
                          )),
                        )
                      ) : historic ? (
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
                              onClick={() => {
                                setView("tree");
                                setSelected(n.run_id);
                                setSelectedExperiment(String(n.entry_id));
                              }}
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
                        !investigation.runtime &&
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
                  <AnimatePresence
                    onExitComplete={() => {
                      const run = closingRun.current;
                      if (run && !pendingView.current)
                        document
                          .querySelector<HTMLButtonElement>(
                            `.react-flow__node[data-id="${CSS.escape(run)}"] .agent-button`,
                          )
                          ?.focus({ preventScroll: true });
                      closingRun.current = null;
                      if (pendingView.current) {
                        setView(pendingView.current);
                        pendingView.current = null;
                      }
                    }}
                  >
                    {selected && view === "tree" && (
                      <motion.article
                        key={selected}
                        ref={workspace}
                        layoutId={`researcher-${selected}`}
                        className="researcher-workspace-overlay inline-research-detail nodrag nowheel nopan"
                        aria-label="Expanded researcher workspace"
                        style={{ borderRadius: 12 }}
                        transition={
                          reducedMotion
                            ? { duration: 0 }
                            : { type: "spring", stiffness: 320, damping: 34 }
                        }
                      >
                        <div className="workspace-titlebar">
                          <span title={selectedTitle}>
                            <GitBranch size={15} />
                            <strong>{selectedTitle}</strong>
                          </span>
                          <Button
                            data-workspace-close
                            size="sm"
                            variant="ghost"
                            aria-label="Close researcher detail"
                            onClick={closeResearcher}
                          >
                            Back to tree <X size={16} />
                          </Button>
                        </div>
                        <motion.div
                          className="expanded-research-content"
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          transition={{ duration: reducedMotion ? 0 : 0.18 }}
                        >
                          {investigation.runtime ? (
                            <RuntimeDetail
                              experimentId={selectedExperiment}
                              runId={selected}
                              run={runtimeState.runs[selected]}
                              project={project}
                              cursor={historic ? runtimeState.sequence : null}
                              replayTime={visibleEvents.at(-1)?.t}
                              connection={runtime.connection}
                              onClose={closeResearcher}
                            />
                          ) : (
                            <AgentDetail
                              initialTab="experiments"
                              runId={selected}
                              summary={visibleRuns.find(
                                (r) => r.run_id === selected,
                              )}
                              experiments={
                                tree.data?.nodes.filter(
                                  (n) => n.run_id === selected,
                                ) || []
                              }
                              onClose={closeResearcher}
                              historic={historic}
                              events={visibleEvents}
                            />
                          )}
                        </motion.div>
                      </motion.article>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </LayoutGroup>
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
              <select
                aria-label="Playback speed"
                value={playbackSpeed}
                onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
              >
                {[0.5, 1, 2, 4, 8, 16].map((speed) => (
                  <option key={speed} value={speed}>
                    {speed}×
                  </option>
                ))}
              </select>
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
  initialTab = "activity",
  runId,
  summary,
  experiments,
  onClose,
  historic,
  events,
}: {
  initialTab?: string;
  runId: string;
  summary?: RunSummary;
  experiments: Experiment[];
  onClose: () => void;
  historic: boolean;
  events: JsonRecord[];
}) {
  const { run, error, connection } = useAgent(historic ? null : runId);
  const [tab, setTab] = useState("activity");
  useEffect(() => setTab(initialTab), [initialTab]);
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
