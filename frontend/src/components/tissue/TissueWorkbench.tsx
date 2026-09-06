import { Fragment, useEffect, useRef, useState, useMemo } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import TissueScene from "./TissueScene";
import {
  initialView,
  conditionIndices,
  sampleField,
  type Tissue,
  type View,
  type Frame,
} from "./types";
import "./tissue.css";
import AgentPlayback, { type SceneAction } from "./AgentPlayback";
import { saveFigure } from "./figure";
import FieldSlice from "./FieldSlice";

export default function TissueWorkbench({
  url,
  owner,
  actions = [],
  embedded = false,
}: {
  url: string;
  owner: string;
  actions?: SceneAction[];
  embedded?: boolean;
}) {
  const [data, setData] = useState<Tissue | null>(null),
    [error, setError] = useState(""),
    [open, setOpen] = useState(false),
    [view, setView] = useState<View>({...initialView,theme:document.documentElement.dataset.theme==='light'?'light':'dark'}),
    [light, setLight] = useState(
      document.documentElement.dataset.theme === "light",
    );
  const host = useRef<HTMLDivElement>(null);
  const cache = useRef(new Map<string, Frame>());
  const [loadingFrame, setLoadingFrame] = useState(false);
  const readyCount = useRef(0);
  const [ready, setReady] = useState(false);
  const [canvasHeight, setCanvasHeight] = useState(0);
  const listedCells =
    data?.conditions[view.condition]?.frames[view.frame]?.cells;
  const cellOptions = useMemo(
    () =>
      listedCells?.map((c) => (
        <option key={c.id} value={c.id}>
          {c.type} #{c.id}
        </option>
      )),
    [listedCells],
  );
  const [small, setSmall] = useState(matchMedia("(max-width:650px)").matches);
  useEffect(() => {
    const m = matchMedia("(max-width:650px)");
    const update = () => {
      setSmall(m.matches);
      if (m.matches) setView((v) => ({ ...v, comparison: false }));
    };
    m.addEventListener("change", update);
    return () => m.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    setData(null);
    cache.current.clear();
    setError("");
    fetch(url, { signal: abort.signal })
      .then(async (r) => {
        if (!r.ok) throw Error("Tissue artifact unavailable");
        const d = await r.json();
        if (
          d.kind !== "tissue_simulation" ||
          d.schema_version !== 1 ||
          !d.conditions?.length
        )
          throw Error("Unsupported tissue artifact");
        setData(d);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [url]);
  useEffect(() => {
    const m = new MutationObserver(() => {
      const theme=document.documentElement.dataset.theme==='light'?'light':'dark';
      setLight(theme==='light');readyCount.current=0;setReady(false);
      if(host.current)host.current.dataset.ready='false';
      setView(v=>({...v,theme}));
    });
    m.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => m.disconnect();
  }, []);
  useEffect(() => {
    if (!data || (data as any).chunked !== true) return;
    let canceled = false;
    const indices = conditionIndices(view);
    setLoadingFrame(true);
    setReady(false);
    readyCount.current = 0;
    Promise.all(
      indices.map(async (ci) => {
        const fi = Math.min(view.frame, data.conditions[ci].frames.length - 1),
          key = `${ci}:${fi}`;
        let frame = cache.current.get(key);
        if (!frame) {
          const endpoint = new URL(
            url.replace("/blob/", "/tissue/"),
            location.origin,
          );
          endpoint.searchParams.set("condition", String(ci));
          endpoint.searchParams.set("frame", String(fi));
          endpoint.searchParams.set("part", "metadata");
          const fieldEndpoint = new URL(endpoint);
          fieldEndpoint.searchParams.set("part", "field");
          const [r, fieldResponse] = await Promise.all([
            fetch(endpoint),
            fetch(fieldEndpoint),
          ]);
          if (!r.ok || !fieldResponse.ok)
            throw Error("Tissue frame unavailable");
          frame = await r.json();
          const bytes = await fieldResponse.arrayBuffer();
          if (
            !frame ||
            bytes.byteLength !==
              frame.field.dimensions.reduce((a, b) => a * b, 4) ||
            bytes.byteLength > 128 ** 3 * 4
          )
            throw Error("Tissue field shape mismatch");
          frame.field.values = Array.from(new Float32Array(bytes));
          cache.current.set(key, frame!);
        }
        return { ci, fi, frame: frame! };
      }),
    )
      .then((items) => {
        if (canceled) return;
        const keep = new Set(items.map((x) => `${x.ci}:${x.fi}`));
        for (const key of cache.current.keys()) {
          if (cache.current.size <= 3) break;
          if (!keep.has(key)) cache.current.delete(key);
        }
        setData((old) =>
          old
            ? {
                ...old,
                conditions: old.conditions.map((c, ci) => ({
                  ...c,
                  frames: c.frames.map(
                    (f, fi) =>
                      items.find((x) => x.ci === ci && x.fi === fi)?.frame ||
                      ({ time: f.time } as Frame),
                  ),
                })),
              }
            : old,
        );
        setLoadingFrame(false);
      })
      .catch((e) => {
        if (!canceled) {
          setError(e.message);
          setLoadingFrame(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [url, Boolean(data), view.frame, view.condition, view.comparison]);
  function change(p: Partial<View>) {
    if (p.theme) document.documentElement.dataset.theme = p.theme;
    if (host.current) host.current.dataset.ready = "false";
    readyCount.current = 0;
    setReady(false);
    setView((v) => ({ ...v, ...p }));
  }
  const markReady = (height: number) => {
    setCanvasHeight(height);
    readyCount.current++;
    if (readyCount.current >= (view.comparison ? 2 : 1)) setReady(true);
  };
  useEffect(() => {
    if (!open && !embedded) return;
    const api = {
      apply: async (p: Partial<View>) => change(p),
      ready: () =>
        new Promise<void>((resolve, reject) => {
          const end = Date.now() + 20000;
          const poll = () => {
            if (host.current?.dataset.ready === "true") resolve();
            else if (Date.now() > end) reject(Error("Tissue render not ready"));
            else requestAnimationFrame(poll);
          };
          poll();
        }),
      capture: () => ({
        png: host.current?.querySelector("canvas")?.toDataURL("image/png"),
        recipe: view,
      }),
    };
    (window as any).tissueReview = api;
    return () => {
      delete (window as any).tissueReview;
    };
  }, [open, embedded, view]);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading tissue experiment…</p>;
  const condition = data.conditions[view.condition],
    frame = condition.frames[Math.min(view.frame, condition.frames.length - 1)],
    selected = frame.cells?.find((c) => c.id === view.selection);
  const neighbors = selected
    ? (frame.cells || []).filter(
        (c) =>
          c.id !== selected.id &&
          c.position.reduce(
            (s, x, i) => s + (x - selected.position[i]) ** 2,
            0,
          ) <=
            35 ** 2,
      )
    : [];
  const indices = conditionIndices(view);
  const Portal = embedded ? Fragment : Dialog.Portal;
  const Content = embedded ? "section" : Dialog.Content;
  const Title = embedded ? "h3" : Dialog.Title;
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      {!embedded && <Dialog.Trigger
        className="tissue-open"
        data-artifact-sha256={new URL(url, location.origin).pathname
          .split("/")
          .pop()}
      >
        Open living tissue <span>Spatial alanine experiment ↗</span>
      </Dialog.Trigger>}
      <Portal>
        {!embedded && <Dialog.Overlay className="tissue-overlay" />}
        <Content
          className={`tissue-workbench ${embedded ? "tissue-embedded" : ""} ${light ? "tissue-light" : ""}`}
          aria-describedby={undefined}
        >
          <header>
            <div>
              <p className="tissue-eyebrow">SPATIAL BIOLOGY / 03</p>
              <Title>Living tissue</Title>
              <p className="tissue-subtitle">{owner}</p>
            </div>
            <div className="tissue-header-actions">
              <span className="tissue-badge">
                {data.category === "illustration"
                  ? "Illustrative fixture"
                  : "Simulation"}
              </span>
              {!embedded && <Dialog.Close aria-label="Return to experiment">✕</Dialog.Close>}
            </div>
          </header>
          <AgentPlayback actions={actions} view={view} apply={change} />
          <div className="tissue-toolbar">
            <nav aria-label="Tissue view">
              {(["Exterior", "Core", "Neighborhood"] as const).map((p) => (
                <button
                  key={p}
                  aria-pressed={view.preset === p}
                  onClick={() =>
                    change({
                      preset: p,
                      section:
                        p === "Exterior"
                          ? 160
                          : p === "Neighborhood"
                            ? (selected?.position[2] || 0) +
                              (selected?.radius || 0)
                            : 0,
                      opacity: p === "Exterior" ? 0 : 0.16,
                      diagnosticSlice: p !== "Exterior",
                      zoom: p === "Neighborhood" ? 1.6 : 1,
                    })
                  }
                >
                  {p}
                </button>
              ))}
            </nav>
            <label>
              <input
                type="checkbox"
                disabled={data.conditions.length < 2 || small}
                checked={view.comparison}
                onChange={(e) => change({ comparison: e.target.checked })}
              />{" "}
              Paired comparison
            </label>
            <button onClick={() => change(initialView)}>Reset view</button>
          </div>
          <div
            ref={host}
            className="tissue-theater"
            data-ready={ready && !loadingFrame}
          >
            {loadingFrame && (
              <p role="status">Loading exact simulation frame…</p>
            )}
            {indices.map((idx) => {
              const c = data.conditions[idx],
                f = c.frames[Math.min(view.frame, c.frames.length - 1)],
                alive = (f.cells || []).filter(
                  (x) => x.type === "tumor" && x.state === "alive",
                ).length;
              return (
                <div
                  className={`tissue-condition ${view.diagnosticSlice ? "has-slice" : ""}`}
                  key={c.id}
                >
                  <div className="tissue-condition-title">
                    <span>
                      0{idx + 1} / {c.label}
                    </span>
                    <strong>
                      {alive.toLocaleString()}{" "}
                      <small>living tumor cells · whole volume</small>
                    </strong>
                  </div>
                  {f.cells && !loadingFrame && (
                    <TissueScene
                      data={data}
                      frame={f}
                      view={view}
                      light={light}
                      onSelect={(id) => change({ selection: id })}
                      onChange={change}
                      ready={markReady}
                    />
                  )}
                  <div
                    className="tissue-scale"
                    style={{
                      width: `${(50 / ((2 * Math.tan((20 * Math.PI) / 180) * 490) / view.zoom)) * canvasHeight}px`,
                    }}
                  >
                    50 µm <small>focal plane</small>
                  </div>
                  <div className="tissue-scene-caption">
                    <span>
                      {view.preset === "Exterior"
                        ? "Exterior · CAF shape is illustrative"
                        : `Cutaway z ≤ ${Number.isInteger(view.section) ? view.section : view.section.toFixed(1)} µm · exact source radii`}
                    </span>
                    <span>{f.time.toLocaleString()} min</span>
                  </div>
                  {view.diagnosticSlice && f.cells && (
                    <FieldSlice
                      frame={f}
                      domain={data.domain}
                      z={view.section}
                      maximum={view.fieldMaximum}
                    />
                  )}
                </div>
              );
            })}
            <div className="tissue-legend">
              <span>
                <i className="tumor-key" />
                Living tumor · pearl
              </span>
              <span>
                <i className="caf-key" />
                CAF
              </span>
              <span>
                <i className="dead-key" />
                Dead tumor · violet
              </span>
              <span className="field-key">
                Alanine <b /> 0 · {(view.fieldMaximum / 2).toFixed(2)} ·{" "}
                {view.fieldMaximum} mM · fixed shared range
              </span>
            </div>
          </div>
          <div className="tissue-bottom">
            <section className="tissue-controls">
              <label>
                Exact frame <output>{frame.time} min</output>
                <input
                  aria-label="Simulation time"
                  type="range"
                  min="0"
                  max={condition.frames.length - 1}
                  value={view.frame}
                  onChange={(e) => change({ frame: +e.target.value })}
                />
              </label>
              <label>
                Section z{" "}
                <output>
                  {Number.isInteger(view.section)
                    ? view.section
                    : view.section.toFixed(1)}{" "}
                  µm
                </output>
                <input
                  aria-label="Section plane"
                  type="range"
                  min="-160"
                  max="160"
                  value={view.section}
                  onChange={(e) => change({ section: +e.target.value })}
                />
              </label>
              <label>
                Field opacity <output>{Math.round(view.opacity * 100)}%</output>
                <input
                  aria-label="Field opacity"
                  type="range"
                  min="0"
                  max="1"
                  step=".02"
                  value={view.opacity}
                  onChange={(e) => change({ opacity: +e.target.value })}
                />
              </label>
              <label>
                Condition
                <select
                  value={view.condition}
                  onChange={(e) =>
                    change({ condition: +e.target.value, comparison: false })
                  }
                >
                  {data.conditions.map((c, i) => (
                    <option key={c.id} value={i}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
            </section>
            <section className="tissue-inspection">
              <details className="tissue-scene-inspector">
                <summary>Scene inspector</summary>
                <label>
                  Shared alanine maximum (mM)
                  <input
                    aria-label="Shared alanine maximum"
                    type="number"
                    min="0.001"
                    max="1000"
                    step="0.01"
                    value={view.fieldMaximum}
                    onChange={(e) => {
                      const v = +e.target.value;
                      if (v >= 0.001 && v <= 1000) change({ fieldMaximum: v });
                    }}
                  />
                </label>
                <label>
                  <input
                    aria-label="Diagnostic alanine slice"
                    type="checkbox"
                    checked={view.diagnosticSlice}
                    onChange={(e) =>
                      change({ diagnosticSlice: e.target.checked })
                    }
                  />{" "}
                  Exact diagnostic slice
                </label>
                <p>
                  Volume and slice use one fixed range across compared
                  conditions. The slice reports saturated voxels. CAF elongation
                  and membrane shading are illustrative.
                </p>
              </details>
              <label>
                Inspect cell
                <select
                  aria-label="Selected cell"
                  value={view.selection ?? ""}
                  onChange={(e) =>
                    change({
                      selection: e.target.value === "" ? null : +e.target.value,
                    })
                  }
                >
                  <option value="">Select in the scene</option>
                  {cellOptions}
                </select>
              </label>
              {selected ? (
                <p>
                  <strong>
                    {selected.type} #{selected.id} · {selected.state}
                  </strong>
                  <br />
                  {sampleField(frame, data.domain, selected.position).toFixed(
                    4,
                  )}{" "}
                  mM local alanine · radius {selected.radius.toFixed(1)} µm
                  <br />
                  Parent {selected.parent_id ?? "founder"} · neighborhood radius
                  35 µm · {neighbors.length} neighbors (
                  {neighbors.filter((c) => c.type === "CAF").length} CAFs)
                </p>
              ) : (
                <p>
                  Orbit by dragging. Scroll to explore the core.
                  <br />
                  Selection and time are shared across paired conditions.
                </p>
              )}
            </section>
          </div>
          <footer>
            <p>
              Conditional model · {(frame.cells?.length || 0).toLocaleString()}{" "}
              cells · µm coordinates · shared field scale
            </p>
            <details>
              <summary>Model, sources & numerical results</summary>
              <pre>
                {JSON.stringify(
                  { provenance: data.provenance, analysis: data.analysis },
                  null,
                  2,
                )}
              </pre>
            </details>
            <button
              onClick={() => {
                if (host.current)
                  saveFigure(
                    host.current,
                    data,
                    view,
                    owner,
                    new URL(url, location.origin).pathname.split("/").pop()!,
                  );
              }}
            >
              Save scene PNG
            </button>
          </footer>
        </Content>
      </Portal>
    </Dialog.Root>
  );
}
