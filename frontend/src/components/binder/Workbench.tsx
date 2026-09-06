import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import Stage, { type StageHandle } from "./Stage";
import CompareStage, { type ComparisonHandle } from "./CompareStage";
import { requireComparable } from "./comparison";
import {
  type Bundle,
  type Preset,
  type SceneState,
  type SceneAction,
  type SurfaceMesh,
  type CameraRecipe,
  label,
} from "./types";
import "./binder.css";
import { hasBackboneTrace } from "./SourceMesh";

const presets: Preset[] = [
  "hero",
  "epitope",
  "interface-close",
  "reverse",
  "exploded",
  "candidate-compare",
  "small-screen",
];
const download = (text: string, name: string, type = "application/json") => {
  const u = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  URL.revokeObjectURL(u);
};
function parseBundle(
  text: string,
  sha256: string,
  signal: AbortSignal,
): Promise<{ bundle: Bundle; meshes: Record<string, SurfaceMesh> }> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./bundle.worker.ts", import.meta.url), {
      type: "module",
    });
    const abort = () => {
      worker.terminate();
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", abort, { once: true });
    const finish = () => {
      signal.removeEventListener("abort", abort);
      worker.terminate();
    };
    worker.onmessage = ({ data }) => {
      finish();
      data.error ? reject(Error(data.error)) : resolve(data);
    };
    worker.onerror = () => {
      finish();
      reject(Error("Candidate parsing worker failed"));
    };
    worker.postMessage({ text, sha256 });
  });
}
export default function Workbench({
  url,
  sha256,
  sceneActions = [],
  candidates = [],
}: {
  url: string;
  sha256: string;
  sceneActions?: SceneAction[];
  candidates?: { sha256: string; name: string; url: string }[];
}) {
  const [bundle, setBundle] = useState<Bundle | null>(null),
    [error, setError] = useState("");
  const traceSupported = useMemo(
    () => (bundle ? hasBackboneTrace(bundle) : false),
    [bundle],
  );
  const [meshes, setMeshes] = useState<Record<string, SurfaceMesh>>({});
  const [state, setState] = useState<SceneState>({
    preset: "hero",
    style: "pearl",
    selected: null,
    revision: 0,
  });
  const [comparison, setComparison] = useState<null | { key: string; bundle: Bundle; meshes: Record<string, SurfaceMesh> }>(null);
  const [comparisonError, setComparisonError] = useState("");
  const comparisonSource = candidates.find(c => c.sha256 === state.comparison_bundle_sha256 && c.sha256 !== sha256);
  useEffect(() => {
    const controller = new AbortController();
    setComparison(null); setComparisonError("");
    if (!state.comparison_bundle_sha256 || !bundle) return () => controller.abort();
    if (!comparisonSource) { setComparisonError("Comparison source unavailable at this experiment cursor."); return () => controller.abort(); }
    void (async () => {
      const response = await fetch(comparisonSource.url, { signal: controller.signal });
      if (!response.ok) throw Error("Comparison source unavailable at this cursor.");
      const parsed = await parseBundle(await response.text(), comparisonSource.sha256, controller.signal);
      requireComparable(bundle, parsed.bundle);
      const bothSurfaces = meshes.target && meshes.binder && parsed.meshes.target && parsed.meshes.binder;
      if (state.representation === "surface" && !bothSurfaces) throw Error("Matching surface meshes unavailable; choose atoms for comparison.");
      if (state.representation === "ribbon" && !hasBackboneTrace(parsed.bundle)) throw Error("Matching backbone traces unavailable; choose atoms for comparison.");
      if (!state.representation && !bothSurfaces) setState(s => ({ ...s, representation: "atoms" }));
      if (!controller.signal.aborted) setComparison({ key: comparisonSource.sha256, ...parsed });
    })().catch(e => { if (!controller.signal.aborted) setComparisonError(e.message); });
    return () => controller.abort();
  }, [bundle, state.comparison_bundle_sha256, comparisonSource?.url, sha256, state.representation, meshes]);
  const paired = comparisonSource && comparison?.key === state.comparison_bundle_sha256 ? comparison : null;
  const comparisonRef = useRef({ paired, error: comparisonError });
  comparisonRef.current = { paired, error: comparisonError };
  const stageElement = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"follow" | "replay" | "explore">("follow");
  const [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [frame, setFrame] = useState(0);
  const recorded = useMemo(
    () => sceneActions.filter((a) => presets.includes(a.view.preset)).map(a => ({ ...a,
      view: { comparison_bundle_sha256: null, comparison_selected: null, ...a.view } })),
    [sceneActions],
  );
  const previousRecordedCount = useRef(0);
  const recordedKey = recorded.map((a) => a.recipe_sha256).join(",");
  const explore = useCallback(() => {
    setMode("explore");
    setPlaying(false);
  }, []);
  useEffect(() => {
    const rewound = recorded.length < previousRecordedCount.current;
    previousRecordedCount.current = recorded.length;
    if (mode === "follow" && recorded.length) {
      const index = recorded.length - 1;
      setFrame(index);
      setState((s) => ({
        ...s,
        ...recorded[index].view,
        revision: s.revision + 1,
      }));
    }
    if (rewound || (recorded.length > 0 && frame >= recorded.length)) {
      setFrame(Math.max(0, recorded.length - 1));
      setPlaying(false);
      setMode("follow");
      setState((s) => ({
        ...s,
        ...(recorded.at(-1)?.view ?? {
          preset: "hero",
          style: "pearl",
          selected: null,
          camera: null,
          comparison_bundle_sha256: null,
          comparison_selected: null,
        }),
        revision: s.revision + 1,
      }));
    }
  }, [recordedKey, mode]);
  useEffect(() => {
    if (!playing || mode !== "replay") return;
    const timer = setTimeout(() => {
      const next = frame + 1;
      if (next >= recorded.length) {
        setPlaying(false);
        return;
      }
      setFrame(next);
      setState((s) => ({
        ...s,
        ...recorded[next].view,
        revision: s.revision + 1,
      }));
    }, 1000 / speed);
    return () => clearTimeout(timer);
  }, [playing, mode, frame, speed, recordedKey]);
  const replayFrame = (index: number) => {
    setMode("replay");
    setFrame(index);
    setState((s) => ({
      ...s,
      ...recorded[index].view,
      revision: s.revision + 1,
    }));
  };
  const handle = useRef<StageHandle | ComparisonHandle | null>(null),
    stateRef = useRef(state);
  stateRef.current = state;
  const [loaded, setLoaded] = useState(false),
    [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setBundle(null);
    setError("");
    setLoaded(false);
    (async () => {
      const r = await fetch(url, { signal: controller.signal });
      if (!r.ok)
        throw Error("This candidate is unavailable at the selected event.");
      const parsed = await parseBundle(
        await r.text(),
        sha256,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setBundle(parsed.bundle);
        setMeshes(parsed.meshes);
      }
    })().catch((e) => {
      if (!controller.signal.aborted) setError(String(e.message));
    });
    return () => controller.abort();
  }, [url, sha256]);
  const onHandle = useCallback((h: StageHandle | ComparisonHandle | null) => {
    handle.current = h;
    h?.ready().then(() => {
      if (handle.current === h) setLoaded(true);
    });
  }, []);
  const onPick = useCallback(
    (id: string) => {
      explore();
      setState((s) => ({ ...s, selected: id, comparison_selected: null }));
    },
    [explore],
  );
  const onOtherPick = useCallback((id: string) => {
    explore(); setState(s => ({ ...s, selected: null, comparison_selected: id }));
  }, [explore]);
  useEffect(() => {
    if (!bundle || !stageElement.current) return;
    const w = window as unknown as { sceneReview?: unknown };
    const bridge = {
      apply: async (patch: Partial<SceneState>) => {
        if (
          patch.representation &&
          !["atoms", "surface", "ribbon"].includes(patch.representation)
        )
          throw Error("Unknown molecular representation");
        if (patch.representation === "ribbon" && !traceSupported)
          throw Error("Connected C-alpha trace unavailable");
        if (
          patch.representation === "surface" &&
          (!meshes.target || !meshes.binder)
        )
          throw Error("No precomputed surface in this bundle");
        if (patch.preset && !presets.includes(patch.preset))
          throw Error("Unknown preset");
        if (patch.style && !["pearl", "copper"].includes(patch.style))
          throw Error("Unknown material");
        if (
          patch.selected &&
          !bundle.structure.residues.some((r) => r.id === patch.selected)
        )
          throw Error("Unknown residue");
        if (
          patch.camera &&
          !["position", "target"].every(
            (k) =>
              Array.isArray(patch.camera![k as "position" | "target"]) &&
              patch.camera![k as "position" | "target"].length === 3 &&
              patch.camera![k as "position" | "target"].every(Number.isFinite),
          )
        )
          throw Error("Invalid camera");
        setLoaded(false);
        setMode("explore");
        setPlaying(false);
        setState((s) => ({
          ...s,
          ...patch,
          camera: patch.camera ?? null,
          revision: s.revision + 1,
        }));
        await new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        );
      },
      ready: async () => {
        const deadline = performance.now() + 30000;
        for (;;) {
          if (comparisonRef.current.error) throw Error(comparisonRef.current.error);
          if (performance.now() > deadline) throw Error("Scene initialization timed out");
          const requested = stateRef.current.comparison_bundle_sha256 || undefined;
          const current = handle.current;
          if (current && (current as ComparisonHandle).comparisonSource === requested &&
            (!requested || comparisonRef.current.paired)) {
            if (stateRef.current.comparison_selected && !comparisonRef.current.paired?.bundle.structure.residues.some(r => r.id === stateRef.current.comparison_selected))
              throw Error("Unknown comparison residue selection");
            await current.ready();
            if (current === handle.current && requested === (stateRef.current.comparison_bundle_sha256 || undefined)) return;
          }
          await new Promise(requestAnimationFrame);
        }
      },
      inspect: () => {
        const {
          camera: _camera,
          representation: _representation,
          ...view
        } = stateRef.current;
        return {
          ...handle.current?.inspect(),
          ...view,
          bundle_sha256: sha256,
        };
      },
      pick: (x: number, y: number) => {
        const id = handle.current?.pick(x, y);
        if (id && typeof id === "object") {
          if (id.bundle_sha256 === sha256) onPick(id.residue_id); else onOtherPick(id.residue_id);
        } else if (id) onPick(id);
        return id;
      },
      capture: () => handle.current?.capture(),
    };
    const element = stageElement.current as HTMLDivElement & {
      binderController?: typeof bridge;
    };
    element.binderController = bridge;
    if (
      import.meta.env.DEV &&
      new URLSearchParams(location.search).get("sceneReview") === "1"
    )
      w.sceneReview = bridge;
    return () => {
      if (w.sceneReview === bridge) delete w.sceneReview;
      if (element.binderController === bridge) delete element.binderController;
    };
  }, [sha256, onPick, onOtherPick, bundle, meshes, traceSupported]);
  if (error) return <p role="alert">{error}</p>;
  if (!bundle) return <p role="status">Opening candidate coordinates…</p>;
  const inspectedBundle = state.comparison_selected && paired ? paired.bundle : bundle;
  const inspectedSelection = (paired ? state.comparison_selected : null) ?? state.selected;
  const residues = new Map(inspectedBundle.structure.residues.map((r) => [r.id, r]));
  const contacts = inspectedBundle.metrics.contacts.filter(
    (c) => c.distance_angstrom <= 4.5,
  );
  const ids = [
    ...new Set(contacts.flatMap((c) => [c.target_residue, c.binder_residue])),
  ];
  const selected = inspectedSelection ? residues.get(inspectedSelection) : null;
  const rows = inspectedSelection
    ? contacts.filter(
        (c) =>
          c.target_residue === inspectedSelection ||
          c.binder_residue === inspectedSelection,
      )
    : contacts;
  return (
    <section
      className={`binder-workbench ${expanded ? "binder-expanded" : ""}`}
      data-bundle-sha256={sha256}
      aria-label="Interface Foundry"
    >
      <header className="binder-heading">
        <div>
          <span className="binder-eyebrow">STRUCTURAL EXPLORATION / 01</span>
          <h3>Interface Foundry</h3>
          <p>Inspect the geometry. Decide the next experiment.</p>
        </div>
        <button onClick={() => setExpanded(!expanded)}>
          {expanded ? "Compact view" : "Expand workbench"}
        </button>
      </header>
      <div
        className="binder-timeline"
        aria-label="Recorded agent scene actions"
      >
        <div>
          <strong>
            {mode === "explore"
              ? "Your exploration"
              : mode === "replay"
                ? "Agent scene replay"
                : "Following agent"}
          </strong>
          <span>Scene actions, not physical time</span>
        </div>
        {recorded.length ? (
          <>
            <button
              onClick={() => {
                if (mode !== "replay" || frame === recorded.length - 1)
                  replayFrame(0);
                setMode("replay");
                setPlaying(!playing);
              }}
            >
              {playing ? "Pause scene replay" : "Replay agent inspection"}
            </button>
            <input
              aria-label="Agent scene action"
              type="range"
              min={0}
              max={recorded.length - 1}
              value={frame}
              onChange={(e) => {
                setPlaying(false);
                replayFrame(Number(e.target.value));
              }}
            />
            <label>
              Playback speed
              <select
                aria-label="Scene playback speed"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
              >
                {[0.25, 0.5, 1, 2, 4].map((n) => (
                  <option key={n} value={n}>
                    {n}×
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => {
                setPlaying(false);
                setMode("follow");
              }}
            >
              Follow latest agent view
            </button>
            <p>
              {frame + 1}/{recorded.length} · {recorded[frame]?.note}
            </p>
          </>
        ) : (
          <p>
            No agent scene actions recorded at this point. Explore the saved
            candidate.
          </p>
        )}
        {mode === "explore" && recorded.length > 0 && (
          <small>
            Your changes are local; the agent's recorded inspection is
            preserved.
          </small>
        )}
      </div>
      {(candidates.some(c => c.sha256 !== sha256) || state.comparison_bundle_sha256) && <label className="binder-compare-select">Compare candidate
        <select aria-label="Compare candidate" value={state.comparison_bundle_sha256 ?? ""}
          onChange={e => { explore(); setState(s => ({ ...s, comparison_bundle_sha256: e.target.value || null,
            comparison_selected: null, camera: null, preset: e.target.value ? "candidate-compare" : "hero", revision: s.revision + 1 })); }}>
          <option value="">Single candidate</option>
          {candidates.filter(c => c.sha256 !== sha256).map(c => <option key={c.sha256} value={c.sha256}>{c.name}</option>)}
        </select>
      </label>}
      {comparisonError && <p role="alert">{comparisonError}</p>}
      {state.comparison_bundle_sha256 && !paired && !comparisonError && <p role="status">Loading aligned comparison…</p>}
      <div className="binder-layout">
        <div className="binder-specimen">
          <div
            ref={stageElement}
            className="binder-stage"
            onPointerDown={explore}
            onWheel={explore}
            data-testid="binder-stage"
            aria-label="Interactive target and binder; exact contacts in table below"
          >
            {paired ? <CompareStage bundle={bundle} other={paired.bundle} sha256={sha256}
              otherSha256={paired.key} meshes={meshes} otherMeshes={paired.meshes} state={state}
              onHandle={onHandle} onPick={onPick} onOtherPick={onOtherPick} /> : (
            <Stage
              meshes={meshes}
              bundle={bundle}
              state={state}
              onHandle={onHandle}
              onPick={onPick}
            />
            )}
            {paired && <div className="binder-compare-names">
              {[bundle, paired.bundle].map((b, i) => <span key={i}>{b.manifest.candidate_id} · {b.manifest.provenance.category.replaceAll("_", " ")}</span>)}
            </div>}
            <div className="binder-caption">
              <span className="binder-badge">
                {paired ? "Exploratory comparison" : bundle.manifest.provenance.category.replaceAll("_", " ")}
              </span>
              <strong>{paired ? "Shared camera · aligned target · same Å scale" : bundle.manifest.candidate_id}</strong>
              <small>
                {state.preset === "exploded"
                  ? "Illustrative separation · measurements use original pose"
                  : ["interface-close", "reverse"].includes(state.preset)
                    ? "Contact-only cutaway · reduced sphere radii · Å"
                    : (state.representation ??
                          (meshes.target ? "surface" : "atoms")) === "surface"
                      ? "Atom-union envelope · approximate surface · Å"
                      : state.representation === "ribbon"
                        ? "Cα trace · interpolated backbone, sidechains omitted · Å"
                        : "Physical coordinates · Å"}
              </small>
            </div>
            <div className="binder-legend">
              <span>
                <i className="target" /> Target
              </span>
              <span>
                <i className="binder" /> Binder
              </span>
              <span>
                <i className="seam" /> Contact patch
              </span>
            </div>
            {!loaded && (
              <span className="binder-loading" role="status">
                Preparing molecular scene…
              </span>
            )}
          </div>
          <nav className="binder-views" aria-label="Molecular camera presets">
            {presets
              .filter((p) => !["candidate-compare", "small-screen"].includes(p))
              .map((p) => (
                <button
                  key={p}
                  aria-pressed={state.preset === p}
                  onClick={() => {
                    explore();
                    setState((s) => ({
                      ...s,
                      preset: p,
                      camera: null,
                      revision: s.revision + 1,
                    }));
                  }}
                >
                  {p.replaceAll("-", " ")}
                </button>
              ))}
          </nav>
          <div
            className="binder-sequence"
            aria-label="Contact residue selection"
          >
            {ids.map((id) => (
              <button
                key={id}
                aria-pressed={inspectedSelection === id}
                onClick={() => inspectedBundle === bundle ? onPick(id) : onOtherPick(id)}
              >
                {label(residues.get(id)!)}
              </button>
            ))}
          </div>
        </div>
        <aside className="binder-inspector">
          <p className="binder-inspected-candidate">Inspecting {inspectedBundle.manifest.candidate_id}</p>
          <span className="binder-eyebrow">INTERFACE INSPECTOR</span>
          <h4>{selected ? label(selected) : "A contact is a measurement"}</h4>
          <p>
            {selected
              ? "Selected by exact residue identity. Contact distances use the saved pose."
              : "Select the specimen or sequence rail to inspect participating residues."}
          </p>
          <dl>
            <div>
              <dt>Heavy-atom pairs ≤4.5 Å</dt>
              <dd>{inspectedBundle.metrics.counts["4.5"]}</dd>
            </div>
            <div>
              <dt>Total buried area</dt>
              <dd>
                {inspectedBundle.metrics.total_buried_area_angstrom2?.toFixed(0) ??
                  "Not measured"}{" "}
                Å²
              </dd>
            </div>
            <div>
              <dt>Pairs below 2.0 Å</dt>
              <dd>{inspectedBundle.metrics.clash_count}</dd>
            </div>
            <div>
              <dt>Binding affinity</dt>
              <dd>Not measured</dd>
            </div>
          </dl>
          <p className="binder-context">
            {bundle.manifest.assembly}.{" "}
            {bundle.manifest.provenance.category === "illustration"
              ? "Illustrative complex; no binder design or biological efficacy is demonstrated."
              : "Exploratory candidate; prediction confidence is not affinity."}
          </p>
          <label>
            Molecular representation
            <select
              aria-label="Molecular representation"
              value={
                state.representation ??
                (meshes.target && meshes.binder ? "surface" : "atoms")
              }
              onChange={(e) => {
                explore();
                setState((s) => ({
                  ...s,
                  representation: e.target.value as
                    "atoms" | "surface" | "ribbon",
                  revision: s.revision + 1,
                }));
              }}
            >
              <option value="atoms">Atomic envelope</option>
              <option
                value="surface"
                disabled={!meshes.target || !meshes.binder}
              >
                Precomputed surface{!meshes.target ? " · unavailable" : ""}
              </option>
              <option value="ribbon" disabled={!traceSupported}>
                Cα backbone trace{!traceSupported ? " · unavailable" : ""}
              </option>
            </select>
          </label>
          <label>
            Camera projection
            <select aria-label="Camera projection" value={state.camera?.projection ?? "PerspectiveCamera"}
              onChange={e => {
                const c = handle.current?.inspect().camera as CameraRecipe | undefined;
                if (!c) return;
                const projection = e.target.value;
                const distance = Math.hypot(...c.position.map((v, i) => v - c.target[i]));
                const height = c.height ?? 2 * distance * Math.tan((c.fov ?? 38) * Math.PI / 360);
                explore(); setState(s => ({ ...s, camera: { position: c.position, target: c.target, up: c.up,
                  near: c.near, far: c.far, projection,
                  ...(projection === "OrthographicCamera" ? { height, zoom: 1 } : { fov: 38 }) },
                  revision: s.revision + 1 }));
              }}>
              <option value="PerspectiveCamera">Perspective</option>
              <option value="OrthographicCamera">Orthographic · constant scale</option>
            </select>
          </label>
          <label>
            Material study
            <select
              value={state.style}
              onChange={(e) => {
                explore();
                setState((s) => ({
                  ...s,
                  style: e.target.value as "pearl" | "copper",
                }));
              }}
            >
              <option value="pearl">Pearl / cyan</option>
              <option value="copper">Bronze / violet</option>
            </select>
          </label>
          <button
            onClick={() =>
              download(
                JSON.stringify(
                  {
                    ...state,
                    ...handle.current?.inspect(),
                    bundle_sha256: sha256,
                    scientific_inputs_read_only: true,
                  },
                  null,
                  2,
                ),
                "scene_recipe.json",
              )
            }
          >
            Export scene recipe
          </button>
          <button
            onClick={() =>
              download(JSON.stringify(bundle), "binder_bundle.json")
            }
          >
            Export candidate bundle
          </button>
        </aside>
      </div>
      {state.preset === "candidate-compare" && !paired && (
        <p className="binder-context">
          Comparison needs a second collected candidate evaluated with the same
          protocol. No second candidate is present in this bundle.
        </p>
      )}
      {paired && <div className="binder-comparison-metrics">
        <table aria-label="Candidate geometry trade-offs">
          <caption>Geometry trade-offs for these two candidates · exploratory, not an affinity rank</caption>
          <thead><tr><th>Candidate</th><th>Pairs ≤4.5 Å</th><th>Pairs &lt;2 Å</th><th>Buried area (Å²)</th><th>Contact/clash Pareto status</th></tr></thead>
          <tbody>{[bundle, paired.bundle].map((b, i, both) => {
            const m = b.metrics, o = both[1-i].metrics;
            const dominated = o.counts["4.5"] >= m.counts["4.5"] && o.clash_count <= m.clash_count &&
              (o.counts["4.5"] > m.counts["4.5"] || o.clash_count < m.clash_count);
            return <tr key={i}><td>{b.manifest.candidate_id}</td><td>{m.counts["4.5"]}</td><td>{m.clash_count}</td>
              <td>{m.total_buried_area_angstrom2?.toFixed(0) ?? "Unavailable"}</td><td>{dominated ? "Dominated on these axes" : "Nondominated among these two"}</td></tr>;
          })}</tbody>
        </table>
      </div>}
      <details className="binder-table" open={Boolean(selected)}>
        <summary>Exact contacts · {rows.length} atom pairs</summary>
        <p>
          Interchain heavy-atom distance rule v1. Sensitivity:{" "}
          {inspectedBundle.metrics.counts["4.0"]} pairs at 4.0 Å;{" "}
          {inspectedBundle.metrics.counts["5.0"]} at 5.0 Å. Buried area: SASA(target) +
          SASA(binder) − SASA(complex), no division by two; 1.4 Å probe, 256
          sphere samples.
        </p>
        <div>
          <table>
            <thead>
              <tr>
                <th>Target residue / atom</th>
                <th>Binder residue / atom</th>
                <th>Distance (Å)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c, i) => (
                <tr key={i}>
                  <td>
                    {label(residues.get(c.target_residue)!)} /{" "}
                    {
                      inspectedBundle.structure.atoms.find((a) => a.id === c.target_atom)
                        ?.name
                    }
                  </td>
                  <td>
                    {label(residues.get(c.binder_residue)!)} /{" "}
                    {
                      inspectedBundle.structure.atoms.find((a) => a.id === c.binder_atom)
                        ?.name
                    }
                  </td>
                  <td>{c.distance_angstrom.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
