import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  ReactFlowProvider,
  useReactFlow,
  Handle,
  Position,
  useInternalNode,
  useStore,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { ArrowLeft, ArrowUpRight, ListFilter, Search, X } from "lucide-react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import {
  asOf,
  attributionLabel,
  CERTAINTY_LABEL,
  claimKey,
  claimSentence,
  curieLink,
  DISPUTE_LABEL,
  edgeWidth,
  EVIDENCE_TYPE_LABEL,
  humanize,
  kindLabel,
  kindShape,
  NOVELTY_LABEL,
  paperLinks,
  polarityLabel,
  polarityMarker,
  PROVENANCE_LABEL,
  relationLabel,
  signGlyph,
  statusExplanation,
  statusTone,
  STUDY_TYPE_LABEL,
  testOutcome,
  type ClaimDetail,
  type ClaimEdge,
  type EngineTest,
  type EntityForm,
  type EvidenceGraph,
  type EvidenceRecord,
  type GraphNode,
  type KindShape,
} from "@/lib/evidence";
import "../evidence.css";
import { useResource } from "@/lib/api";
import { id, number } from "@/lib/utils";
import { Button } from "./ui/button";
import { Disclosure, Empty, ErrorNotice, Loading, Status } from "./common";

// --- glyphs -----------------------------------------------------------------------------------
// Entity kind is carried by shape and text; colour never encodes it (frontend/DESIGN.md).
function KindGlyph({ kind, size = 12 }: { kind?: string; size?: number }) {
  const shape: KindShape = kindShape(kind);
  const c = size / 2;
  const r = size / 2 - 1;
  let body: React.ReactNode;
  switch (shape) {
    case "circle":
      body = <circle cx={c} cy={c} r={r} />;
      break;
    case "diamond":
      body = (
        <path d={`M${c} 1 L${size - 1} ${c} L${c} ${size - 1} L1 ${c} Z`} />
      );
      break;
    case "square":
      body = <rect x={1.5} y={1.5} width={size - 3} height={size - 3} />;
      break;
    case "hexagon":
      body = (
        <path
          d={`M${c} 1 L${size - 1.5} ${size * 0.28} L${size - 1.5} ${size * 0.72} L${c} ${size - 1} L1.5 ${size * 0.72} L1.5 ${size * 0.28} Z`}
        />
      );
      break;
    case "triangle":
      body = (
        <path d={`M${c} 1.5 L${size - 1} ${size - 1.5} L1 ${size - 1.5} Z`} />
      );
      break;
    case "bar":
      body = <rect x={1} y={c - 2} width={size - 2} height={4} />;
      break;
    default:
      body = <circle cx={c} cy={c} r={r - 1.5} strokeDasharray="2 1.5" />;
  }
  return (
    <svg
      className={`kind-glyph kind-${shape}`}
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden="true"
    >
      {body}
    </svg>
  );
}
// The sign of a claim, in the notation biologists already read: arrowhead enables, bar represses,
// an open dot means the predicate carries no sign (binds, associated_with, precedes...).
function PolarityMark({ polarity }: { polarity?: number | null }) {
  const kind = polarityMarker(polarity);
  return (
    <svg
      className="polarity-mark"
      width="34"
      height="12"
      viewBox="0 0 34 12"
      aria-hidden="true"
    >
      <line x1="1" y1="6" x2={kind === "arrow" ? 26 : 27} y2="6" />
      {kind === "arrow" && (
        <path d="M25 1.5 L32 6 L25 10.5 Z" className="fill" />
      )}
      {kind === "tee" && <line x1="30" y1="1" x2="30" y2="11" />}
      {kind === "dot" && <circle cx="30" cy="6" r="3" />}
    </svg>
  );
}
// Marker definitions for React Flow edges: one per sign and per colour role, so a stroke and its
// head always agree. userSpaceOnUse keeps the head the same size at every line weight.
const TONES = ["edge", "attention", "accent"] as const;
function EdgeMarkers() {
  return (
    <svg className="edge-markers" aria-hidden="true">
      <defs>
        {TONES.map((tone) => (
          <g key={tone}>
            <marker
              id={`dn-arrow-${tone}`}
              viewBox="0 0 12 12"
              refX="11"
              refY="6"
              markerWidth="11"
              markerHeight="11"
              markerUnits="userSpaceOnUse"
              orient="auto-start-reverse"
            >
              <path
                d="M1 1.5 L11 6 L1 10.5 Z"
                style={{ fill: `var(--${tone})` }}
              />
            </marker>
            <marker
              id={`dn-tee-${tone}`}
              viewBox="0 0 12 12"
              refX="10"
              refY="6"
              markerWidth="12"
              markerHeight="12"
              markerUnits="userSpaceOnUse"
              orient="auto"
            >
              <rect
                x="8"
                y="0.5"
                width="2.4"
                height="11"
                style={{ fill: `var(--${tone})` }}
              />
            </marker>
            <marker
              id={`dn-dot-${tone}`}
              viewBox="0 0 12 12"
              refX="9"
              refY="6"
              markerWidth="12"
              markerHeight="12"
              markerUnits="userSpaceOnUse"
              orient="auto"
            >
              <circle
                cx="6"
                cy="6"
                r="3.2"
                style={{
                  fill: "var(--stage)",
                  stroke: `var(--${tone})`,
                  strokeWidth: 1.6,
                }}
              />
            </marker>
          </g>
        ))}
      </defs>
    </svg>
  );
}

// --- graph nodes ----------------------------------------------------------------------------
// A knowledge-graph node: the entity's kind is the shape, its size is how many claims touch it in
// this view, the label sits underneath. Colour is reserved for selection.
export function nodeRadius(degree: number): number {
  return Math.min(34, 13 + 5 * Math.sqrt(Math.max(1, degree)));
}
type EntityData = GraphNode & {
  r: number;
  selected: boolean;
  primary: boolean;
  dim: boolean;
  labelZoom: number;
  [key: string]: unknown;
};
function shapePath(shape: KindShape, r: number): React.ReactNode {
  const c = r;
  const k = r - 1.5;
  switch (shape) {
    case "diamond":
      return (
        <path
          d={`M${c} ${c - k} L${c + k} ${c} L${c} ${c + k} L${c - k} ${c} Z`}
        />
      );
    case "square":
      return (
        <rect
          x={c - k * 0.85}
          y={c - k * 0.85}
          width={k * 1.7}
          height={k * 1.7}
          rx={2}
        />
      );
    case "hexagon":
      return (
        <path
          d={`M${c} ${c - k} L${c + k * 0.87} ${c - k / 2} L${c + k * 0.87} ${c + k / 2} L${c} ${c + k} L${c - k * 0.87} ${c + k / 2} L${c - k * 0.87} ${c - k / 2} Z`}
        />
      );
    case "triangle":
      return (
        <path
          d={`M${c} ${c - k} L${c + k * 0.95} ${c + k * 0.7} L${c - k * 0.95} ${c + k * 0.7} Z`}
        />
      );
    case "bar":
      return (
        <rect
          x={c - k}
          y={c - k * 0.45}
          width={k * 2}
          height={k * 0.9}
          rx={3}
        />
      );
    case "ring":
      return <circle cx={c} cy={c} r={k} strokeDasharray="3 2.5" />;
    default:
      return <circle cx={c} cy={c} r={k} />;
  }
}
function EntityNode({ data }: NodeProps<Node<EntityData>>) {
  const zoom = useStore((s) =>
    Math.max(0.05, Math.round(s.transform[2] * 20) / 20),
  );
  const showLabel = data.primary || zoom >= data.labelZoom;
  const size = data.r * 2;
  const claims = data.degree === 1 ? "1 claim" : `${data.degree} claims`;
  return (
    <div
      className={`kg-node ${data.selected ? "selected" : ""} ${data.dim ? "dim" : ""}`}
      style={
        {
          width: size,
          height: size,
          "--node-stroke": `${(data.selected ? 2 : 1) / zoom}px`,
        } as React.CSSProperties
      }
      title={`${data.label} · ${kindLabel(data.kind)} · ${claims}`}
    >
      <Handle type="target" position={Position.Top} />
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden="true"
      >
        {shapePath(kindShape(data.kind), data.r)}
      </svg>
      <span
        className={`kg-label ${showLabel ? "" : "quiet-label"}`}
        style={{ fontSize: 14 / zoom }}
      >
        <strong style={{ maxWidth: 180 / zoom }}>{data.label}</strong>
        {data.primary && data.curie && <code>{data.curie}</code>}
      </span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
const nodeTypes = { entity: EntityNode };

// One claim, drawn between the borders of its two nodes. Several claims between the same two
// entities (a dispute is exactly that) bow apart by `bow` pixels so each keeps its own head, weight
// and label instead of being painted over the other.
type ClaimEdgeData = {
  bow: number;
  dim: boolean;
  active: boolean;
  [key: string]: unknown;
};
function ClaimEdgeView({
  id,
  source,
  target,
  style,
  markerEnd,
  label,
  data,
}: EdgeProps<Edge<ClaimEdgeData>>) {
  const scale = useStore((s) =>
    Math.pow(2, Math.round(Math.log2(s.transform[2]))),
  );
  const far = useStore((s) => s.transform[2] < 0.3);
  const detailed = useStore((s) => s.transform[2] >= 0.35);
  const a = useInternalNode(source);
  const b = useInternalNode(target);
  if (!a || !b) return null;
  const centre = (n: typeof a) => {
    const w = n.measured.width ?? Number((n.data as EntityData).r) * 2;
    const h = n.measured.height ?? w;
    return {
      x: n.internals.positionAbsolute.x + w / 2,
      y: n.internals.positionAbsolute.y + h / 2,
      r: w / 2,
    };
  };
  const p = centre(a);
  const q = centre(b);
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const bow = data?.bow ?? 0;
  // The curve leaves and enters the shapes at their borders, corrected for the bow's pull.
  const sx = p.x + ux * p.r - uy * bow * 0.35;
  const sy = p.y + uy * p.r + ux * bow * 0.35;
  const tx = q.x - ux * (q.r + 1) - uy * bow * 0.35;
  const ty = q.y - uy * (q.r + 1) + ux * bow * 0.35;
  const mx = (sx + tx) / 2 - uy * bow * 2;
  const my = (sy + ty) / 2 + ux * bow * 2;
  const loop = p.r + 50 + Math.abs(bow) * 2 + (bow >= 0 ? 22 : 0);
  const path =
    source === target
      ? `M ${p.x - p.r * 0.7} ${p.y - p.r * 0.7} C ${p.x - loop} ${p.y - loop * 2}, ${p.x + loop} ${p.y - loop * 2}, ${p.x + p.r * 0.7} ${p.y - p.r * 0.7}`
      : `M ${sx} ${sy} Q ${mx} ${my} ${tx} ${ty}`;
  const lx = source === target ? p.x : (sx + tx) / 2 - uy * bow;
  const ly = source === target ? p.y - loop * 1.5 : (sy + ty) / 2 + ux * bow;
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          ...style,
          opacity: data?.dim ? 0.025 : data?.active ? 0.95 : far ? 0.24 : 0.13,
          strokeWidth:
            Number(data?.active ? style?.strokeWidth : far ? 0.65 : 0.8) /
            scale,
        }}
        markerEnd={detailed || data?.active ? (markerEnd as string) : undefined}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            className={`edge-label ${data?.dim ? "dim" : ""} ${data?.active ? "active" : ""}`}
            style={{
              transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)`,
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
const edgeTypes = { claim: ClaimEdgeView };

// Force-directed layout, run to rest before the first paint. Deterministic: the same graph always
// lands in the same place (seeded jitter, fixed tick count), so a reload never rearranges the scene.
type SimNode = SimulationNodeDatum & { id: string; r: number };
function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
export function forceLayout(
  nodes: GraphNode[],
  edges: ClaimEdge[],
): Map<string, { x: number; y: number }> {
  const sim: SimNode[] = nodes.map((n) => ({
    id: n.id,
    r: nodeRadius(n.degree),
  }));
  const ids = new Set(sim.map((n) => n.id));
  const links: (SimulationLinkDatum<SimNode> & { n: number })[] = edges
    .filter(
      (e) => ids.has(e.source) && ids.has(e.target) && e.source !== e.target,
    )
    .map((e) => ({ source: e.source, target: e.target, n: e.n_sources }));
  const spread = 26 * Math.sqrt(Math.max(1, nodes.length));
  forceSimulation(sim)
    .randomSource(seeded(7))
    .force(
      "link",
      forceLink<SimNode, SimulationLinkDatum<SimNode>>(links)
        .id((d) => d.id)
        .distance(190)
        .strength(0.5),
    )
    .force(
      "charge",
      forceManyBody<SimNode>()
        .strength(-820)
        .distanceMax(spread * 4),
    )
    .force("collide", forceCollide<SimNode>((d) => d.r + 62).iterations(2))
    .force("center", forceCenter(0, 0))
    .force("x", forceX<SimNode>(0).strength(0.04))
    .force("y", forceY<SimNode>(0).strength(0.06))
    .stop()
    .tick(360);
  return new Map(
    sim.map((n) => [n.id, { x: (n.x ?? 0) - n.r, y: (n.y ?? 0) - n.r }]),
  );
}

// Greedy label placement in screen space at zoom bands. Every node stays in the graph;
// only its label waits until there is room. Hover and selection always reveal it.
export function labelThresholds(
  nodes: GraphNode[],
  positions: Map<string, { x: number; y: number }>,
) {
  const result = new Map<string, number>();
  const ranked = [...nodes].sort(
    (a, b) => b.degree - a.degree || a.id.localeCompare(b.id),
  );
  for (const zoom of [0.08, 0.15, 0.25, 0.4, 0.65, 1, 1.5, 2]) {
    const boxes: { x: number; y: number; w: number; h: number }[] = [];
    const candidates =
      zoom < 0.25
        ? ranked.slice(0, 12)
        : zoom < 0.4
          ? ranked.slice(0, 60)
          : ranked;
    // Keep labels already admitted at wider zooms before admitting new neighbors.
    const ordered = [...candidates].sort(
      (a, b) => Number(result.has(b.id)) - Number(result.has(a.id)),
    );
    for (const node of ordered) {
      const p = positions.get(node.id);
      if (!p) continue;
      const w = Math.min(180, node.label.length * 7.5) + 16;
      const h = node.label.length * 7.5 > 180 ? 44 : 26;
      const r = nodeRadius(node.degree);
      const box = {
        x: (p.x + r) * zoom - w / 2,
        y: (p.y + r * 2) * zoom + 4,
        w,
        h,
      };
      if (
        boxes.some(
          (b) =>
            box.x < b.x + b.w &&
            box.x + box.w > b.x &&
            box.y < b.y + b.h &&
            box.y + box.h > b.y,
        )
      )
        continue;
      boxes.push(box);
      if (!result.has(node.id)) result.set(node.id, zoom);
    }
  }
  return result;
}

// Highest number of distinct connected neighbors, never claim status or source count.
export function denseCenter(
  nodes: GraphNode[],
  edges: ClaimEdge[],
  positions: Map<string, { x: number; y: number }>,
) {
  const neighbors = new Map(nodes.map((n) => [n.id, new Set<string>()]));
  for (const e of edges) {
    if (e.source === e.target) continue;
    neighbors.get(e.source)?.add(e.target);
    neighbors.get(e.target)?.add(e.source);
  }
  const ranked = [...nodes].sort(
    (a, b) =>
      (neighbors.get(b.id)?.size || 0) - (neighbors.get(a.id)?.size || 0) ||
      a.id.localeCompare(b.id),
  );
  const node = ranked[0];
  const p = node && positions.get(node.id);
  return p
    ? {
        x: p.x + nodeRadius(node.degree),
        y: p.y + nodeRadius(node.degree),
        small: nodes.length <= 24,
      }
    : null;
}

function FocusEvidence({
  ids,
  center,
}: {
  ids: string;
  center: { x: number; y: number; small: boolean } | null;
}) {
  const flow = useReactFlow();
  useEffect(() => {
    if (new URLSearchParams(location.search).get("sceneReview") !== "1") return;
    const target = window as unknown as {
      knowledgeReview?: {
        nodes: typeof flow.getNodes;
        edges: typeof flow.getEdges;
      };
    };
    const review = { nodes: flow.getNodes, edges: flow.getEdges };
    target.knowledgeReview = review;
    return () => {
      if (target.knowledgeReview === review) delete target.knowledgeReview;
    };
  }, [flow]);
  const width = useStore((state) => state.width);
  const height = useStore((state) => state.height);
  const duration = () =>
    matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 250;
  const home = () =>
    center && !center.small
      ? flow.setCenter(center.x, center.y, { zoom: 0.7, duration: duration() })
      : flow.fitView({ padding: 0.18, maxZoom: 1, duration: duration() });
  useEffect(() => {
    if (!width || !height) return;
    const timer = setTimeout(() => {
      if (ids)
        void flow.fitView({
          nodes: JSON.parse(ids).map((id: string) => ({ id })),
          padding: 0.45,
          maxZoom: 1,
          duration: duration(),
        });
      else void home();
    }, 100);
    return () => clearTimeout(timer);
    // Scalar coordinates keep background polling from resetting a manually explored camera.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids, flow, width, height, center?.x, center?.y, center?.small]);
  return (
    <div className="graph-camera-controls">
      <Button onClick={() => void home()}>Connected region</Button>
      <Button
        onClick={() =>
          void flow.fitView({
            padding: 0.12,
            minZoom: 0.015,
            maxZoom: 1,
            duration: duration(),
          })
        }
      >
        Fit all
      </Button>
    </div>
  );
}
function useDebounced<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// --- page -----------------------------------------------------------------------------------
export function Knowledge({ project }: { project: string }) {
  return (
    <div className="evidence-page">
      <Relationships key={project} project={project} />
    </div>
  );
}

const FILTERS_EMPTY = { status: "", polarity: "", kind: "", relation: "" };

function Relationships({ project }: { project: string }) {
  const [source, setSource] = useState(project);
  const [filters, setFilters] = useState(FILTERS_EMPTY);
  const [query, setQuery] = useState("");
  const q = useDebounced(query.trim(), 250);
  const [selected, setSelected] = useState("");
  const [claimId, setClaimId] = useState("");
  const [browse, setBrowse] = useState(false);
  const [hideLeaves, setHideLeaves] = useState(true);

  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelected("");
        setClaimId("");
        setBrowse(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  const params = new URLSearchParams({ complete: "1" });
  if (source) params.set("source", source);
  if (filters.status) params.set("status", filters.status);
  if (filters.polarity) params.set("polarity", filters.polarity);
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.relation) params.set("relation_class", filters.relation);
  if (q) params.set("q", q);
  const graph = useResource<EvidenceGraph>(`/api/kg?${params}`, 15000);
  const data = graph.data;
  const leaves = useMemo(() => {
    const incident = new Map<string, Set<string>>();
    for (const edge of data?.edges || []) {
      for (const node of new Set([edge.source, edge.target])) {
        if (!incident.has(node)) incident.set(node, new Set());
        incident.get(node)!.add(claimKey(edge));
      }
    }
    return new Set(
      [...incident].filter(([, claims]) => claims.size === 1).map(([id]) => id),
    );
  }, [data]);
  const visibleEdges = (data?.edges || []).filter(
    (e) => !hideLeaves || (!leaves.has(e.source) && !leaves.has(e.target)),
  );
  const visibleNodeCount = (data?.nodes || []).filter(
    (n) => !hideLeaves || !leaves.has(n.id),
  ).length;
  const labels = useMemo(
    () => new Map(data?.nodes.map((n) => [n.id, n.label])),
    [data],
  );
  const nodesById = useMemo(
    () => new Map(data?.nodes.map((n) => [n.id, n])),
    [data],
  );
  const claim = data?.edges.find((e) => claimKey(e) === claimId);
  const entity = nodesById.get(selected);
  const related =
    visibleEdges.filter(
      (e) => !selected || e.source === selected || e.target === selected,
    ) || [];
  const focused = new Set(
    claim
      ? [claim.source, claim.target]
      : selected
        ? [selected, ...related.flatMap((e) => [e.source, e.target])]
        : [],
  );
  const focusIds = focused.size ? JSON.stringify([...focused].sort()) : "";
  const topology = JSON.stringify([
    data?.nodes.map((n) => [n.id, n.degree]),
    data?.edges.map((e) => [e.source, e.target]),
  ]);
  const positions = useMemo(
    () => (data ? forceLayout(data.nodes, data.edges) : new Map()),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topology],
  );
  const anyFocus = Boolean(claimId || selected);
  const labelZooms = useMemo(
    () => labelThresholds(data?.nodes || [], positions),
    [data, positions],
  );
  const center = useMemo(
    () => denseCenter(data?.nodes || [], data?.edges || [], positions),
    [data, positions],
  );
  const nodes: Node<EntityData>[] =
    data?.nodes.map((n) => {
      const r = nodeRadius(n.degree);
      return {
        id: n.id,
        type: "entity",
        hidden: hideLeaves && leaves.has(n.id),
        position: positions.get(n.id) || { x: 0, y: 0 },
        width: r * 2,
        height: r * 2,
        measured: { width: r * 2, height: r * 2 },
        handles: [
          {
            type: "source",
            position: Position.Bottom,
            x: r,
            y: r,
            width: 1,
            height: 1,
          },
          {
            type: "target",
            position: Position.Top,
            x: r,
            y: r,
            width: 1,
            height: 1,
          },
        ],
        style: { width: r * 2, height: r * 2 },
        data: {
          ...n,
          r,
          labelZoom: labelZooms.get(n.id) ?? Infinity,
          selected: focused.has(n.id),
          primary: claim
            ? n.id === claim.source || n.id === claim.target
            : n.id === selected,
          dim: anyFocus && !focused.has(n.id),
        },
      };
    }) || [];
  // Every predicate is written out on small graphs; larger ones label the selection, and the
  // on-demand browser names every claim in view.
  const labelAll = (data?.edges.length || 0) <= 18;
  // Bow claims that share a pair of endpoints (in either direction) apart from one another. The
  // sign is fixed by the canonical endpoint order so two opposite claims never land on one side.
  const bows = useMemo(() => {
    const groups = new Map<string, string[]>();
    data?.edges.forEach((e) => {
      const key = [e.source, e.target].sort().join("\u0000");
      groups.set(key, [...(groups.get(key) || []), claimKey(e)]);
    });
    const out = new Map<string, number>();
    groups.forEach((keys) =>
      keys.forEach((k, i) => out.set(k, (i - (keys.length - 1) / 2) * 22)),
    );
    return out;
  }, [data]);
  const edges: Edge<ClaimEdgeData>[] =
    data?.edges.map((e) => {
      const key = claimKey(e);
      const active = claim
        ? key === claimId
        : selected
          ? e.source === selected || e.target === selected
          : false;
      const dim = anyFocus && !active;
      const tone =
        e.status === "disputed" ? "attention" : active ? "accent" : "edge";
      const width = edgeWidth(e.n_sources) + (active ? 0.6 : 0);
      const bow = (bows.get(key) || 0) * (e.source < e.target ? 1 : -1);
      return {
        id: key,
        source: e.source,
        target: e.target,
        type: "claim",
        hidden: hideLeaves && (leaves.has(e.source) || leaves.has(e.target)),
        data: { bow, dim, active },
        label: (claim ? active : labelAll)
          ? humanize(e.predicate).toLowerCase()
          : undefined,
        ariaLabel: `${claimSentence(e, labels)}. ${polarityLabel(e.polarity)}, ${humanize(e.status).toLowerCase()}, ${e.n_sources} ${e.n_sources === 1 ? "source" : "sources"}. Inspect evidence`,
        markerEnd: `dn-${polarityMarker(e.polarity)}-${tone}`,
        style: {
          stroke: `var(--${tone})`,
          strokeWidth: width,
          opacity: dim ? 0.14 : 0.9,
          strokeDasharray: e.status === "disputed" ? "6 4" : undefined,
        },
      };
    }) || [];
  const inspect = (e: ClaimEdge) => {
    setClaimId(claimKey(e));
    setBrowse(true);
  };
  const choose = (nodeId: string) => {
    setSelected(nodeId);
    setClaimId("");
    setBrowse(true);
  };
  const clear = () => {
    setSelected("");
    setClaimId("");
    setBrowse(false);
  };
  const filtered = Boolean(
    q || filters.status || filters.polarity || filters.kind || filters.relation,
  );
  const setFilter = (key: keyof typeof FILTERS_EMPTY, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    clear();
  };
  const facet = (name: string) => data?.facets?.[name] || [];
  const kindsInView = [
    ...new Set(data?.nodes.map((n) => n.kind).filter(Boolean)),
  ] as string[];
  return (
    <>
      <div className="evidence-toolbar">
        <h1 className="knowledge-title">Knowledge</h1>
        <label className="search-field">
          <Search size={15} />
          <input
            placeholder="Find an entity or relationship"
            aria-label="Find an entity or relationship"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setClaimId("");
              setSelected("");
              setBrowse(false);
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
                setFilters(FILTERS_EMPTY);
                clear();
              }}
            >
              {data?.sources.map((s) => (
                <option key={s} value={s}>
                  {humanize(s.replace("project:", ""))}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Status
          <select
            aria-label="Claim status"
            value={filters.status}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">All</option>
            {["disputed", "established", "reported"].map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
                {data?.status_counts?.[s] != null
                  ? ` (${number(data.status_counts[s])})`
                  : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sign
          <select
            aria-label="Claim sign"
            value={filters.polarity}
            onChange={(e) => setFilter("polarity", e.target.value)}
          >
            <option value="">All</option>
            {facet("polarity").map((f) => (
              <option key={String(f.value)} value={String(f.value)}>
                {polarityLabel(Number(f.value))} ({number(f.n)})
              </option>
            ))}
          </select>
        </label>
        <label>
          Kind
          <select
            aria-label="Entity kind"
            value={filters.kind}
            onChange={(e) => setFilter("kind", e.target.value)}
          >
            <option value="">All</option>
            {facet("kind").map((f) => (
              <option key={String(f.value)} value={String(f.value)}>
                {kindLabel(String(f.value))} ({number(f.n)})
              </option>
            ))}
          </select>
        </label>
        <label>
          Relation
          <select
            aria-label="Relation class"
            value={filters.relation}
            onChange={(e) => setFilter("relation", e.target.value)}
          >
            <option value="">All</option>
            {facet("relation_class").map((f) => (
              <option key={String(f.value)} value={String(f.value)}>
                {relationLabel(String(f.value))} ({number(f.n)})
              </option>
            ))}
          </select>
        </label>
        <label className="leaf-filter">
          <input
            type="checkbox"
            checked={hideLeaves}
            onChange={(e) => {
              setHideLeaves(e.target.checked);
              clear();
            }}
          />
          Hide single-claim nodes
        </label>
        <span className="muted view-count" aria-live="polite">
          {graph.loading && !data && "Loading all claims and entities…"}
          {data?.shown != null &&
            (filtered
              ? `${number(data.shown)} / ${number(data.matched)} matching claims loaded · ${number(data.nodes.length)} entities`
              : `${number(data.shown)} / ${number(data.total_claims)} claims loaded · ${number(data.nodes.length)} entities`)}
          {data && (
            <span className="visible-count">
              Showing {number(visibleEdges.length)} claims ·{" "}
              {number(visibleNodeCount)} entities
            </span>
          )}
        </span>
      </div>
      {data?.summary && <CollectionStrip data={data} />}
      <ErrorNotice
        message={
          graph.error ||
          (data && data.shown !== data.matched
            ? "Incomplete graph response. Reload with a server supporting complete collection retrieval."
            : undefined)
        }
        retry={graph.refresh}
      />
      {graph.loading && !data ? (
        <Loading />
      ) : !data?.nodes.length ? (
        filtered ? (
          <Empty
            title="No claims match"
            action={
              <Button
                onClick={() => {
                  setFilters(FILTERS_EMPTY);
                  setQuery("");
                  clear();
                }}
              >
                Clear search and filters
              </Button>
            }
          >
            The search covers the whole collection, not only the claims already
            drawn.
          </Empty>
        ) : (
          <Empty title="No relationships to explore yet">
            Build a literature collection to connect its claims and entities.
          </Empty>
        )
      ) : (
        <div
          className={`relationships-layout evidence-explorer ${browse ? "browsing" : ""}`}
        >
          <div className="relationship-canvas">
            <EdgeMarkers />
            <div className="relationship-map">
              <div className="evidence-map-caption">
                <strong>Literature relationships</strong>
                <span>
                  {data.shown === data.matched
                    ? "All matching relationships loaded."
                    : "Incomplete response; reload to retrieve the complete graph."}{" "}
                  {hideLeaves
                    ? "Single-claim nodes and their claims are hidden."
                    : "Zoom for detail; fit all to see every component."}
                </span>
              </div>
              <ReactFlowProvider>
                <ReactFlow
                  key={`${source}:${q}:${JSON.stringify(filters)}`}
                  nodes={nodes}
                  edges={edges}
                  nodeTypes={nodeTypes}
                  edgeTypes={edgeTypes}
                  fitView
                  fitViewOptions={{ padding: 0.18, maxZoom: 1.1 }}
                  minZoom={0.015}
                  maxZoom={2}
                  nodesConnectable={false}
                  nodesDraggable={false}
                  onlyRenderVisibleElements
                  onNodeClick={(_, n) => choose(n.id)}
                  onEdgeClick={(_, e) => {
                    const found = data.edges.find((c) => claimKey(c) === e.id);
                    if (found) inspect(found);
                  }}
                  onPaneClick={clear}
                >
                  <FocusEvidence ids={focusIds} center={center} />
                  <Background gap={24} size={0.6} color="var(--grid)" />
                  <Controls showInteractive={false} showFitView={false} />
                </ReactFlow>
              </ReactFlowProvider>
              <Button
                className="browse-evidence"
                onClick={() => setBrowse(true)}
              >
                <ListFilter size={15} />
                Browse {related.length}{" "}
                {related.length === 1 ? "relationship" : "relationships"}
              </Button>
            </div>
            <Legend kinds={kindsInView} />
          </div>
          {browse && (
            <aside
              className="detail-panel evidence-inspector"
              aria-label="Relationship evidence"
            >
              <div className="detail-head">
                <span>
                  {claim
                    ? "Claim & sources"
                    : entity
                      ? "Entity & relationships"
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
              <div
                className="detail-scroll"
                key={claimId || selected || "browse"}
              >
                {claim ? (
                  <ClaimView
                    key={claimKey(claim)}
                    edge={claim}
                    source={data.source || source}
                    labels={labels}
                    nodesById={nodesById}
                    edges={data.edges}
                    onBack={() => setClaimId("")}
                    onEntity={choose}
                    onClaim={inspect}
                  />
                ) : entity ? (
                  <EntityView
                    node={entity}
                    edges={related}
                    labels={labels}
                    onClaim={inspect}
                    onEntity={choose}
                  />
                ) : (
                  <>
                    <h2>
                      {q ? "Matching relationships" : "Read the connections"}
                    </h2>
                    <p className="muted">
                      {related.length}{" "}
                      {related.length === 1 ? "relationship" : "relationships"}
                      {q
                        ? ` matching “${q}” across the collection`
                        : filtered
                          ? " matching the filters"
                          : " in view"}
                      . Choose one to inspect its sources, context and tests.
                    </p>
                    {related.length === 0 && (
                      <p>
                        No matching relationships in this view. Try another term
                        or claim filter.
                      </p>
                    )}
                    <ClaimList
                      edges={related}
                      labels={labels}
                      onClaim={inspect}
                    />
                  </>
                )}
              </div>
            </aside>
          )}
        </div>
      )}
    </>
  );
}

// The collection in numbers. Every figure is a count read from the graph file, with the file's
// modification time as its "as of"; a table the collection lacks says so instead of showing 0.
function CollectionStrip({ data }: { data: EvidenceGraph }) {
  const s = data.summary!;
  const fig = (n: number | null | undefined, unit: string, one = unit) =>
    n == null ? null : (
      <span key={unit}>
        <b>{number(n)}</b> {n === 1 ? one : unit}
      </span>
    );
  return (
    <div
      className="knowledge-strip"
      aria-label="Collection summary"
      title={`Graph updated ${asOf(data.as_of)}`}
    >
      {fig(s.claims, "claims", "claim")}
      {fig(s.entities, "entities", "entity")}
      {fig(s.evidence, "evidence records", "evidence record")}
      {s.papers != null && (
        <span>
          <b>{number(s.papers)}</b> {s.papers === 1 ? "paper" : "papers"}
          {s.papers_full_text != null && (
            <small> ({number(s.papers_full_text)} full text)</small>
          )}
        </span>
      )}
      {fig(s.experiments, "reported experiments", "reported experiment")}
      {fig(s.tests, "engine tests", "engine test")}
      {s.deferrals
        ? fig(s.deferrals, "deferred extractions", "deferred extraction")
        : null}
      <span className="muted as-of">
        {data.source
          ? `${humanize(data.source.replace("project:", ""))} graph, `
          : ""}
        as of {asOf(data.as_of)}
      </span>
    </div>
  );
}

function Legend({ kinds }: { kinds: string[] }) {
  return (
    <div className="evidence-legend" aria-label="Legend">
      <div className="legend-group">
        <span className="legend-item">
          <PolarityMark polarity={1} /> enables
        </span>
        <span className="legend-item">
          <PolarityMark polarity={-1} /> represses
        </span>
        <span className="legend-item">
          <PolarityMark polarity={0} /> no sign
        </span>
      </div>
      <div className="legend-group">
        <span className="legend-item">
          <svg
            width="34"
            height="12"
            viewBox="0 0 34 12"
            aria-hidden="true"
            className="legend-line"
          >
            <line x1="1" y1="6" x2="33" y2="6" strokeWidth={1.2} />
          </svg>
          1 source
        </span>
        <span className="legend-item">
          <svg
            width="34"
            height="12"
            viewBox="0 0 34 12"
            aria-hidden="true"
            className="legend-line"
          >
            <line x1="1" y1="6" x2="33" y2="6" strokeWidth={1.8} />
          </svg>
          2–3
        </span>
        <span className="legend-item">
          <svg
            width="34"
            height="12"
            viewBox="0 0 34 12"
            aria-hidden="true"
            className="legend-line"
          >
            <line x1="1" y1="6" x2="33" y2="6" strokeWidth={2.6} />
          </svg>
          4+
        </span>
        <span className="legend-item disputed-key">
          <svg
            width="34"
            height="12"
            viewBox="0 0 34 12"
            aria-hidden="true"
            className="legend-line"
          >
            <line
              x1="1"
              y1="6"
              x2="33"
              y2="6"
              strokeWidth={1.8}
              strokeDasharray="6 4"
            />
          </svg>
          dashed = disputed in corpus
        </span>
      </div>
      {kinds.length > 0 && (
        <div className="legend-group">
          {kinds.map((k) => (
            <span className="legend-item" key={k}>
              <KindGlyph kind={k} /> {kindLabel(k).toLowerCase()}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// --- lists ----------------------------------------------------------------------------------
function TestedTag({ edge }: { edge: ClaimEdge }) {
  const t = edge.tested;
  if (!t) return null;
  const parts = [];
  if (t.validated) parts.push(`${t.validated} accepted`);
  if (t.rejected) parts.push(`${t.rejected} rejected`);
  if (t.candidate) parts.push(`${t.candidate} awaiting review`);
  if (t.killed) parts.push(`${t.killed} failed`);
  return (
    <span className="tested-tag" title="Engine tests on this claim">
      tested: {parts.join(", ")}
    </span>
  );
}
function ClaimList({
  edges,
  labels,
  onClaim,
}: {
  edges: ClaimEdge[];
  labels: Map<string, string>;
  onClaim: (e: ClaimEdge) => void;
}) {
  return (
    <div className="claim-results">
      {edges.map((e) => (
        <button
          className="claim-result"
          key={claimKey(e)}
          onClick={() => onClaim(e)}
        >
          <span className="claim-result-head">
            <Status label={humanize(e.status)} tone={statusTone(e.status)} />
            <PolarityMark polarity={e.polarity} />
            <small>{polarityLabel(e.polarity).toLowerCase()}</small>
            {e.relation_class && (
              <small>· {relationLabel(e.relation_class).toLowerCase()}</small>
            )}
          </span>
          <strong>{claimSentence(e, labels)}</strong>
          <span className="claim-result-foot">
            <span>
              {e.n_sources} {e.n_sources === 1 ? "source" : "sources"}
              {e.first_year ? ` · first ${e.first_year}` : ""}
            </span>
            <TestedTag edge={e} />
            <ArrowUpRight size={14} />
          </span>
        </button>
      ))}
    </div>
  );
}

function EntityView({
  node,
  edges,
  labels,
  onClaim,
  onEntity,
}: {
  node: GraphNode;
  edges: ClaimEdge[];
  labels: Map<string, string>;
  onClaim: (e: ClaimEdge) => void;
  onEntity: (id: string) => void;
}) {
  const out = edges.filter((e) => e.source === node.id);
  const inc = edges.filter((e) => e.target === node.id && e.source !== node.id);
  const link = curieLink(node.curie);
  const neighbours = [
    ...new Set(edges.flatMap((e) => [e.source, e.target])),
  ].filter((n) => n !== node.id);
  return (
    <>
      <div className="entity-head">
        <KindGlyph kind={node.kind} size={18} />
        <div>
          <h2>{node.label}</h2>
          <p className="muted">
            {kindLabel(node.kind)}
            {node.curie && (
              <>
                {" · "}
                {link ? (
                  <a
                    href={link}
                    target="_blank"
                    rel="noreferrer"
                    className="curie"
                  >
                    {node.curie} <ArrowUpRight size={12} />
                  </a>
                ) : (
                  <code className="curie">{node.curie}</code>
                )}
              </>
            )}
          </p>
        </div>
      </div>
      <dl className="facts">
        <div>
          <dt>Claims in view</dt>
          <dd>
            {edges.length} ({out.length} as subject, {inc.length} as object)
          </dd>
        </div>
        <div>
          <dt>Connected to</dt>
          <dd>
            {neighbours.length === 0
              ? "Nothing in view"
              : neighbours.map((n, i) => (
                  <span key={n}>
                    {i > 0 && ", "}
                    <button className="inline-link" onClick={() => onEntity(n)}>
                      {labels.get(n) || n}
                    </button>
                  </span>
                ))}
          </dd>
        </div>
      </dl>
      {out.length > 0 && (
        <>
          <h3 className="list-heading">As subject</h3>
          <ClaimList edges={out} labels={labels} onClaim={onClaim} />
        </>
      )}
      {inc.length > 0 && (
        <>
          <h3 className="list-heading">As object</h3>
          <ClaimList edges={inc} labels={labels} onClaim={onClaim} />
        </>
      )}
      {edges.length === 0 && (
        <p>No claims about this entity are in the current view.</p>
      )}
    </>
  );
}

// --- one claim ------------------------------------------------------------------------------
function FormLine({ form }: { form?: EntityForm }) {
  if (!form || !Object.keys(form).length) return null;
  const bits = [
    form.state && form.state !== "unknown"
      ? humanize(form.state).toLowerCase()
      : "",
    form.variant,
    form.isoform,
    form.protein_construct ? `construct ${form.protein_construct}` : "",
    form.feature_type ? `feature ${form.feature_type}` : "",
  ].filter(Boolean);
  return bits.length ? (
    <small className="entity-form">{bits.join(" · ")}</small>
  ) : null;
}
function SpineEntity({
  label,
  kind,
  curie,
  form,
  onClick,
}: {
  label: string;
  kind?: string;
  curie?: string;
  form?: EntityForm;
  onClick?: () => void;
}) {
  const link = curieLink(curie);
  return (
    <div className="spine-entity">
      <KindGlyph kind={kind} size={14} />
      <span>
        <button className="spine-name" onClick={onClick} disabled={!onClick}>
          <strong>{label}</strong>
        </button>
        <small>
          {kindLabel(kind)}
          {curie &&
            (link ? (
              <a href={link} target="_blank" rel="noreferrer" className="curie">
                {curie} <ArrowUpRight size={11} />
              </a>
            ) : (
              <code>{curie}</code>
            ))}
        </small>
        <FormLine form={form} />
      </span>
    </div>
  );
}
function ClaimView({
  edge,
  source,
  labels,
  nodesById,
  edges,
  onBack,
  onEntity,
  onClaim,
}: {
  edge: ClaimEdge;
  source: string;
  labels: Map<string, string>;
  nodesById: Map<string, GraphNode>;
  edges: ClaimEdge[];
  onBack: () => void;
  onEntity: (id: string) => void;
  onClaim: (e: ClaimEdge) => void;
}) {
  const detail = useResource<ClaimDetail>(
    edge.claim_id && source
      ? `/api/kg?source=${id(source)}&claim=${id(edge.claim_id)}`
      : null,
  );
  const c = detail.data?.claim;
  const subject = nodesById.get(edge.source);
  const object = nodesById.get(edge.target);
  const aspect = c?.object_function ?? edge.object_function;
  const relation = c?.relation_class ?? edge.relation_class;
  const mechanism = c?.mechanism ?? edge.mechanism;
  const firstYear = c?.first_year ?? edge.first_year;
  const disputeKind = c?.dispute_kind ?? edge.dispute_kind;
  const related = detail.data?.related?.length
    ? detail.data.related
    : edges
        .filter(
          (e) =>
            e.abstract_key &&
            e.abstract_key === edge.abstract_key &&
            claimKey(e) !== claimKey(edge),
        )
        .map((e) => ({
          claim_id: e.claim_id || claimKey(e),
          subject_label: labels.get(e.source) || e.source,
          predicate: e.predicate,
          object_label: labels.get(e.target) || e.target,
          object_function: e.object_function,
          relation_class: e.relation_class,
          polarity: e.polarity,
          status: e.status,
          dispute_kind: e.dispute_kind,
          n_sources: e.n_sources,
          first_year: e.first_year,
        }));
  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="back-to-claims"
        onClick={onBack}
      >
        <ArrowLeft size={14} />
        Back to connections
      </Button>
      <div className="claim-status">
        <Status label={humanize(edge.status)} tone={statusTone(edge.status)} />
        <p className="status-note">
          {statusExplanation(edge.status, disputeKind)}
        </p>
      </div>
      <h2 className="selected-claim-title">{claimSentence(edge, labels)}</h2>
      <div className="spine">
        <SpineEntity
          label={labels.get(edge.source) || edge.source}
          kind={c?.subject_kind ?? subject?.kind}
          curie={c?.subject_curie ?? subject?.curie}
          form={c?.subject_form}
          onClick={() => onEntity(edge.source)}
        />
        <div className="spine-relation">
          <PolarityMark polarity={edge.polarity} />
          <strong>{humanize(edge.predicate).toLowerCase()}</strong>
          <small>
            {polarityLabel(edge.polarity)} · {relationLabel(relation)}
          </small>
        </div>
        <SpineEntity
          label={labels.get(edge.target) || edge.target}
          kind={c?.object_kind ?? object?.kind}
          curie={c?.object_curie ?? object?.curie}
          form={c?.object_form}
          onClick={
            edge.target !== edge.source
              ? () => onEntity(edge.target)
              : undefined
          }
        />
      </div>
      <dl className="facts">
        <div>
          <dt>Measured as</dt>
          <dd>{aspect ? humanize(aspect) : "The object itself"}</dd>
        </div>
        <div>
          <dt>Sources</dt>
          <dd>
            {edge.n_sources} distinct{" "}
            {edge.n_sources === 1 ? "source" : "sources"} in this collection
          </dd>
        </div>
        <div>
          <dt>First mentioned</dt>
          <dd>{firstYear || "Year not recorded"}</dd>
        </div>
        <div>
          <dt>Mechanism</dt>
          <dd>{mechanism || "Not recorded"}</dd>
        </div>
        {disputeKind && (
          <div>
            <dt>Dispute</dt>
            <dd>{DISPUTE_LABEL[disputeKind] || humanize(disputeKind)}</dd>
          </div>
        )}
      </dl>
      {related.length > 0 && (
        <section
          className="related-claims"
          aria-label="Other answers to the same question"
        >
          <h3>Same question, other answers</h3>
          <div className="claim-results compact">
            {related.map((r) => {
              const inView = edges.find((e) => e.claim_id === r.claim_id);
              return (
                <button
                  className="claim-result"
                  key={r.claim_id}
                  disabled={!inView}
                  onClick={() => inView && onClaim(inView)}
                  title={inView ? undefined : "Not in the current view"}
                >
                  <span className="claim-result-head">
                    <Status
                      label={humanize(r.status)}
                      tone={statusTone(r.status)}
                    />
                    <PolarityMark polarity={r.polarity} />
                    <small>{polarityLabel(r.polarity).toLowerCase()}</small>
                  </span>
                  <strong>
                    {r.subject_label} {humanize(r.predicate).toLowerCase()}{" "}
                    {r.object_label}
                    {r.object_function
                      ? ` (${humanize(r.object_function).toLowerCase()})`
                      : ""}
                  </strong>
                  <span className="claim-result-foot">
                    <span>
                      {r.n_sources} {r.n_sources === 1 ? "source" : "sources"}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      )}
      <EngineTests tests={detail.data?.tests} loading={detail.loading} />
      <ClaimSources edge={edge} detail={detail} />
    </>
  );
}

function EngineTests({
  tests,
  loading,
}: {
  tests?: EngineTest[];
  loading: boolean;
}) {
  return (
    <section className="engine-tests" aria-label="Engine tests">
      <h3>Tested by the engine</h3>
      {loading && !tests && <Loading label="Loading tests" />}
      {tests && tests.length === 0 && (
        <p className="muted">No experiment has tested this relationship yet.</p>
      )}
      {tests?.map((t) => {
        const outcome = testOutcome(t);
        return (
          <article className="engine-test" key={t.test_id}>
            <header>
              <strong>{humanize(t.method)}</strong>
              <Status label={outcome.label} tone={outcome.tone} />
            </header>
            {t.hypothesis && <p className="hypothesis">{t.hypothesis}</p>}
            <dl className="measurements compact">
              <div>
                <dt>Predicted</dt>
                <dd className="sign">{signGlyph(t.expected_sign)}</dd>
              </div>
              <div>
                <dt>Observed</dt>
                <dd className="sign">{signGlyph(t.observed_sign)}</dd>
              </div>
              <div>
                <dt>
                  Effect <small>method units</small>
                </dt>
                <dd>{number(t.effect)}</dd>
              </div>
              <div>
                <dt>Null-test p</dt>
                <dd>{number(t.p_null)}</dd>
              </div>
            </dl>
            <p className="outcome-detail">{outcome.detail}</p>
            {t.novelty_verdict && (
              <p className="muted">
                Novelty:{" "}
                {NOVELTY_LABEL[t.novelty_verdict] ||
                  humanize(t.novelty_verdict)}
              </p>
            )}
            <Disclosure title="Run and test IDs">
              <dl className="dev-ids">
                <div>
                  <dt>Run</dt>
                  <dd>
                    <code>{t.run_id}</code>
                  </dd>
                </div>
                <div>
                  <dt>Test</dt>
                  <dd>
                    <code>{t.test_id}</code>
                  </dd>
                </div>
                {t.verdict_note && (
                  <div>
                    <dt>Verdict note</dt>
                    <dd>{t.verdict_note}</dd>
                  </div>
                )}
              </dl>
            </Disclosure>
          </article>
        );
      })}
    </section>
  );
}

function ClaimSources({
  edge,
  detail,
}: {
  edge: ClaimEdge;
  detail: ReturnType<typeof useResource<ClaimDetail>>;
}) {
  if (!edge.claim_id)
    return (
      <p className="muted">
        Source inspection is unavailable for this older graph response. Refresh
        after updating the server.
      </p>
    );
  const d = detail.data;
  return (
    <section className="claim-sources" aria-label="Supporting evidence">
      <h3>What the sources say</h3>
      <ErrorNotice message={detail.error} retry={detail.refresh} />
      {detail.loading && <Loading label="Loading source evidence" />}
      {d && (
        <p className="muted">
          {d.evidence.length} of {d.evidence_total} stored evidence{" "}
          {d.evidence_total === 1 ? "record" : "records"}. Quotations keep their
          original wording; the labels below are the extractor's readings of
          them.
        </p>
      )}
      {d?.evidence.length === 0 && (
        <p>No quoted evidence is stored for this relationship.</p>
      )}
      {d?.evidence.map((e, i) => (
        <EvidenceRecordView record={e} index={i + 1} key={e.evidence_id} />
      ))}
      {d && (
        <Disclosure title="Claim identifiers">
          <dl className="dev-ids">
            <div>
              <dt>Claim</dt>
              <dd>
                <code>{d.claim.claim_id}</code>
              </dd>
            </div>
            {d.claim.abstract_key && (
              <div>
                <dt>Question key</dt>
                <dd>
                  <code>{d.claim.abstract_key}</code>
                </dd>
              </div>
            )}
            {d.claim.created_at && (
              <div>
                <dt>Stored</dt>
                <dd>{d.claim.created_at}</dd>
              </div>
            )}
          </dl>
        </Disclosure>
      )}
    </section>
  );
}

function Agreement({ agreed }: { agreed?: boolean | null }) {
  if (agreed == null) return null;
  return (
    <small>
      {agreed ? "model and checker agreed" : "model and checker disagreed"}
    </small>
  );
}
function EvidenceRecordView({
  record: e,
  index,
}: {
  record: EvidenceRecord;
  index: number;
}) {
  const wording = [
    e.predicate ? `“${e.predicate}”` : "",
    e.aspect_said
      ? `aspect said: ${humanize(e.aspect_said).toLowerCase()}`
      : "",
    e.mechanism_term
      ? `route: ${humanize(e.mechanism_term).toLowerCase()}`
      : "",
    e.quantifier ? `quantifier: ${e.quantifier}` : "",
  ].filter(Boolean);
  const x = e.experiment;
  return (
    <article className="source-evidence">
      <header>
        <span className="source-ref">Record {index}</span>
        <span>{e.section || "Section not recorded"}</span>
        <span>{e.experiment_id ? "Reports an experiment" : "Retelling"}</span>
      </header>
      {e.papers.length ? (
        e.papers.map((p) => {
          const links = paperLinks(p);
          return (
            <div className="source-paper" key={p.paper_id}>
              <h4>{p.title || e.source_label || "Untitled source"}</h4>
              <div className="source-paper-meta">
                <span>{p.year || "Year not recorded"}</span>
                {p.is_full_text != null && (
                  <span>
                    {p.is_full_text ? "Full text stored" : "Abstract only"}
                  </span>
                )}
                {p.license && <span>{p.license}</span>}
                {links.map((l) => (
                  <a
                    href={l.href}
                    target="_blank"
                    rel="noreferrer"
                    key={l.label}
                  >
                    {l.label} <ArrowUpRight size={12} />
                  </a>
                ))}
              </div>
              {p.meta_verified === false && (
                <small>Source identity has not been verified.</small>
              )}
            </div>
          );
        })
      ) : (
        <h4>{e.source_label || "Source metadata not stored"}</h4>
      )}
      {e.quote ? (
        <blockquote>{e.quote}</blockquote>
      ) : (
        <p className="muted">No source quotation stored.</p>
      )}
      <dl className="evidence-attributes">
        <div>
          <dt>Evidence type</dt>
          <dd>
            {e.evidence_type
              ? EVIDENCE_TYPE_LABEL[e.evidence_type] ||
                humanize(e.evidence_type)
              : "Not recorded"}
          </dd>
        </div>
        <div>
          <dt>Study type</dt>
          <dd>
            {e.study_type
              ? STUDY_TYPE_LABEL[e.study_type] || humanize(e.study_type)
              : "Not recorded"}
          </dd>
        </div>
        <div>
          <dt>Attribution</dt>
          <dd>
            {attributionLabel(e.attribution)}{" "}
            <Agreement agreed={e.attribution_agreed} />
          </dd>
        </div>
        <div>
          <dt>Certainty</dt>
          <dd>
            {e.certainty
              ? CERTAINTY_LABEL[e.certainty] || humanize(e.certainty)
              : "Not recorded"}{" "}
            <Agreement agreed={e.certainty_agreed} />
          </dd>
        </div>
        {wording.length > 0 && (
          <div>
            <dt>Source wording</dt>
            <dd>{wording.join(" · ")}</dd>
          </div>
        )}
        {e.cites && e.cites.length > 0 && (
          <div>
            <dt>Leans on</dt>
            <dd>
              {e.cites.map((c) => (
                <code key={`${c.sid}${c.marker}`}>
                  {c.sid}
                  {c.marker ? ` ${c.marker}` : ""}
                </code>
              ))}
            </dd>
          </div>
        )}
      </dl>
      {x && (
        <div className="reported-experiment">
          <h5>Experiment reported by this source</h5>
          <dl className="evidence-attributes">
            {(
              [
                ["Unit", x.unit],
                ["Intervention", x.intervention],
                ["Control", x.control],
                ["Readout", x.readout],
                ["Assay", x.assay ? humanize(x.assay) : ""],
                ["Timepoint", x.timepoint ? humanize(x.timepoint) : ""],
                ["n", x.n == null ? "" : String(x.n)],
                ["Effect", x.effect],
                ["Uncertainty", x.uncertainty],
                ["Statistic", x.statistic],
              ] as [string, string | undefined][]
            )
              .filter(([, v]) => v)
              .map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
          </dl>
          {x.quote && <q>{x.quote}</q>}
        </div>
      )}
      {e.contexts.length > 0 && (
        <details className="source-context" open>
          <summary>Biological context</summary>
          <dl>
            {e.contexts.map((c) => (
              <div key={c.ctx_id}>
                <dt>{humanize(c.slot)}</dt>
                <dd>
                  {c.label || humanize(c.value)}
                  {c.label && c.value !== c.label && <code>{c.value}</code>}
                  <small>
                    {PROVENANCE_LABEL[c.provenance || "unspecified"] ||
                      humanize(c.provenance)}
                    {c.inherited_from ? ` (${c.inherited_from})` : ""}
                  </small>
                  {c.quote && <q>{c.quote}</q>}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      <Disclosure title="Extraction record">
        <dl className="dev-ids">
          <div>
            <dt>Evidence</dt>
            <dd>
              <code>{e.evidence_id}</code>
            </dd>
          </div>
          <div>
            <dt>Source ref</dt>
            <dd>
              <code>{e.source_ref}</code>
            </dd>
          </div>
          {e.extractor && (
            <div>
              <dt>Extractor</dt>
              <dd>
                {e.extractor}
                {e.prompt_version ? ` · prompt ${e.prompt_version}` : ""}
              </dd>
            </div>
          )}
          {e.attribution_basis && (
            <div>
              <dt>Attribution basis</dt>
              <dd>{e.attribution_basis.split(";").join(", ")}</dd>
            </div>
          )}
          {e.certainty_basis && (
            <div>
              <dt>Certainty basis</dt>
              <dd>{e.certainty_basis.split(";").join(", ")}</dd>
            </div>
          )}
        </dl>
      </Disclosure>
    </article>
  );
}
