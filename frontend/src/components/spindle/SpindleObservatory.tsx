import { useCallback, useEffect, useRef, useState } from "react";
import SpindleScene, { type RenderState } from "./SpindleScene";
import {
  validateBundle,
  type SpindleBundle,
  type SpindleRecipe,
  type Vec3,
} from "./types";
import "./spindle.css";
type SceneAction = {
  sequence: number;
  note: string;
  recipe_sha256: string;
  view: Partial<SpindleRecipe>;
};
export default function SpindleObservatory({
  url,
  sha256,
  sceneActions = [],
}: {
  url: string;
  sha256?: string;
  sceneActions?: SceneAction[];
}) {
  const [bundle, setBundle] = useState<SpindleBundle>(),
    [error, setError] = useState(""),
    [expanded, setExpanded] = useState(false),
    [readyRevision, setReadyRevision] = useState(-1);
  const [recipe, setRecipe] = useState<SpindleRecipe>({
    frame: 0,
    run: 0,
    selected: null,
    shot: "oblique",
    treatment: "luminous",
    trails: true,
    revision: 0,
  });
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const otherCanvas = useRef<HTMLCanvasElement | null>(null);
  const stage = useRef<HTMLDivElement | null>(null);
  const actual = useRef<RenderState | null>(null);
  const otherActual = useRef<RenderState | null>(null),
    firstRevision = useRef(-1),
    otherRevision = useRef(-1);
  const stateRef = useRef(recipe);
  stateRef.current = recipe;
  const loadedRef = useRef(-1);
  loadedRef.current = readyRevision;
  const [mode, setMode] = useState("explore"),
    [actionIndex, setActionIndex] = useState(0),
    [contextLost, setContextLost] = useState(false),
    [generation, setGeneration] = useState(0);
  const recordedKey = sceneActions.map((a) => a.recipe_sha256).join("|");
  useEffect(() => {
    if (mode === "follow" && sceneActions.length) {
      const i = sceneActions.length - 1;
      setActionIndex(i);
      setRecipe((r) => ({
        ...r,
        ...sceneActions[i].view,
        revision: r.revision + 1,
      }));
    }
    if (actionIndex >= sceneActions.length && mode === "replay") {
      setMode("follow");
      setActionIndex(Math.max(0, sceneActions.length - 1));
      setRecipe((r) => ({
        ...r,
        ...(sceneActions.at(-1)?.view ?? {
          run: 0,
          frame: 0,
          selected: null,
          camera: null,
        }),
        revision: r.revision + 1,
      }));
    }
  }, [recordedKey, mode]);
  useEffect(() => {
    if (!bundle || !stage.current) return;
    const el = stage.current as HTMLDivElement & {
      spindleController?: unknown;
    };
    const bridge = {
      apply: async (view: Partial<SpindleRecipe>) => {
        const merged = { ...stateRef.current, ...view };
        if (!bundle.runs[merged.run]?.frames[merged.frame])
          throw Error("Unknown saved frame");
        if (
          !["front", "oblique", "detail"].includes(merged.shot) ||
          !["luminous", "fine"].includes(merged.treatment)
        )
          throw Error("Unsupported view");
        if (
          merged.selected &&
          !bundle.runs[merged.run].frames[merged.frame].poles.some(
            (p) => p.id === merged.selected,
          )
        )
          throw Error("Unknown pole");
        if (
          merged.camera &&
          ![merged.camera.position, merged.camera.target].every(
            (v) =>
              Array.isArray(v) && v.length === 3 && v.every(Number.isFinite),
          )
        )
          throw Error("Invalid camera");
        loadedRef.current = -1;
        setReadyRevision(-1);
        setMode("explore");
        setRecipe((r) => ({ ...r, ...view, revision: r.revision + 1 }));
        await new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        );
      },
      ready: async () => {
        const deadline = performance.now() + 30000;
        while (
          loadedRef.current !== stateRef.current.revision ||
          !actual.current ||
          !canvas.current ||
          actual.current.viewport.width !== canvas.current.width ||
          actual.current.viewport.height !== canvas.current.height ||
          Math.abs(
            canvas.current.width - canvas.current.getBoundingClientRect().width,
          ) > 1 ||
          Math.abs(
            canvas.current.height -
              canvas.current.getBoundingClientRect().height,
          ) > 1
        ) {
          if (performance.now() > deadline)
            throw Error("Spindle scene unavailable or context lost");
          await new Promise(requestAnimationFrame);
        }
      },
      inspect: () => ({
        ...stateRef.current,
        ...actual.current,
        bundle_sha256: sha256,
        compare: stateRef.current.compare ?? null,
        comparison:
          stateRef.current.compare == null ? null : otherActual.current,
        viewport:
          stateRef.current.compare == null
            ? actual.current?.viewport
            : {
                width: Math.round(el.clientWidth),
                height: Math.round(el.clientHeight),
                dpr: 1,
              },
      }),
      capture: () => canvas.current?.toDataURL("image/png"),
    };
    el.spindleController = bridge;
    return () => {
      if (el.spindleController === bridge) delete el.spindleController;
    };
  }, [bundle, sha256]);
  useEffect(() => {
    const abort = new AbortController();
    setBundle(undefined);
    setError("");
    void fetch(url, { signal: abort.signal })
      .then(async (r) => {
        if (!r.ok) throw Error("Spindle artifact unavailable");
        const raw = await r.text();
        if (raw.length > 20 * 1024 * 1024)
          throw Error("Spindle artifact exceeds display budget");
        if (sha256) {
          const hash = Array.from(
            new Uint8Array(
              await crypto.subtle.digest(
                "SHA-256",
                new TextEncoder().encode(raw),
              ),
            ),
          )
            .map((x) => x.toString(16).padStart(2, "0"))
            .join("");
          if (hash !== sha256) throw Error("Spindle artifact hash mismatch");
        }
        return validateBundle(JSON.parse(raw));
      })
      .then((b) => {
        if (abort.signal.aborted) return;
        setRecipe({
          frame: 0,
          run: 0,
          selected: null,
          shot: "oblique",
          treatment: "luminous",
          trails: true,
          revision: 0,
          ...(mode === "follow" ? sceneActions.at(-1)?.view : {}),
        });
        setBundle(b);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [url, sha256]);
  const patch = useCallback((p: Partial<SpindleRecipe>) => {
    setMode("explore");
    setRecipe((r) => ({ ...r, ...p, revision: r.revision + 1 }));
  }, []);
  const ready = useCallback(
    (c: HTMLCanvasElement, snapshot: RenderState) => {
      if (canvas.current !== c)
        c.addEventListener("webglcontextlost", (e) => {
          e.preventDefault();
          setContextLost(true);
          setReadyRevision(-1);
          loadedRef.current = -1;
          actual.current = null;
        });
      canvas.current = c;
      actual.current = snapshot;
      firstRevision.current = recipe.revision;
      if (recipe.compare != null) setReadyRevision(-1);
      if (recipe.compare == null || otherRevision.current === recipe.revision) {
        loadedRef.current = recipe.revision;
        setReadyRevision(recipe.revision);
      }
    },
    [recipe.revision, recipe.compare],
  );
  const otherReady = useCallback(
    (c: HTMLCanvasElement, snapshot: RenderState) => {
      if (otherCanvas.current !== c)
        c.addEventListener("webglcontextlost", (e) => {
          e.preventDefault();
          setContextLost(true);
          setReadyRevision(-1);
          loadedRef.current = -1;
          otherActual.current = null;
          otherRevision.current = -1;
        });
      otherCanvas.current = c;
      otherActual.current = snapshot;
      otherRevision.current = recipe.revision;
      if (firstRevision.current === recipe.revision) {
        loadedRef.current = recipe.revision;
        setReadyRevision(recipe.revision);
      }
    },
    [recipe.revision],
  );
  const pick = useCallback((id: string) => patch({ selected: id }), [patch]);
  const camera = useCallback(
    (position: Vec3, target: Vec3) => patch({ camera: { position, target } }),
    [patch],
  );
  if (error) return <p role="alert">{error}</p>;
  if (!bundle) return <p role="status">Loading spindle trajectory…</p>;
  const run = bundle.runs[recipe.run],
    frame = run.frames[recipe.frame],
    selected = frame.poles.find((p) => p.id === recipe.selected);
  const otherRun = recipe.compare == null ? null : bundle.runs[recipe.compare];
  let otherFrame = 0;
  otherRun?.frames.forEach((f, i) => {
    if (
      Math.abs(f.time - frame.time) <
      Math.abs(otherRun.frames[otherFrame].time - frame.time)
    )
      otherFrame = i;
  });
  const download = () => {
    if (!canvas.current || readyRevision !== recipe.revision) return;
    const a = document.createElement("a");
    a.download = `spindle-seed-${run.seed}-frame-${recipe.frame}.png`;
    a.href = canvas.current.toDataURL("image/png");
    a.click();
  };
  return (
    <section
      className={`spindle-observatory ${expanded ? "spindle-expanded" : ""}`}
      aria-label="Spindle observatory"
      data-bundle-sha256={sha256}
      data-scene-ready={readyRevision === recipe.revision ? "true" : "false"}
    >
      <header>
        <div>
          <small>SPINDLE OBSERVATORY</small>
          <h3>A geometry of division</h3>
        </div>
        <button onClick={() => setExpanded(!expanded)}>
          {expanded ? "Close expanded view" : "Expand scene"}
        </button>
      </header>
      {sceneActions.length > 0 && (
        <div className="spindle-toolbar" aria-label="Recorded scene actions">
          <button onClick={() => setMode("follow")}>Follow agent</button>
          <label>
            Agent action
            <select
              aria-label="Agent action"
              value={actionIndex}
              onChange={(e) => {
                const i = Number(e.target.value);
                setActionIndex(i);
                setMode("replay");
                setRecipe((r) => ({
                  ...r,
                  ...sceneActions[i].view,
                  revision: r.revision + 1,
                }));
              }}
            >
              {sceneActions.map((a, i) => (
                <option key={a.recipe_sha256} value={i}>
                  {i + 1}. {a.note}
                </option>
              ))}
            </select>
          </label>
          <span>{mode} · scene actions, separate from physical time</span>
        </div>
      )}
      {contextLost && (
        <p role="alert">
          Graphics context lost.{" "}
          <button
            onClick={() => {
              setContextLost(false);
              setGeneration((g) => g + 1);
              patch({});
            }}
          >
            Restore spindle scene
          </button>
        </p>
      )}
      <div
        className={`spindle-stage ${otherRun ? "spindle-comparison" : ""}`}
        ref={stage}
        onContextMenu={(e) => e.preventDefault()}
      >
        <div className="spindle-cell">
          <SpindleScene
            key={generation}
            bundle={bundle}
            recipe={recipe}
            pick={pick}
            ready={ready}
            onCamera={camera}
          />
        </div>
        {otherRun && (
          <div className="spindle-cell">
            <SpindleScene
              key={`comparison-${generation}`}
              bundle={bundle}
              recipe={{
                ...recipe,
                run: recipe.compare!,
                frame: otherFrame,
                camera: recipe.camera ?? actual.current?.camera,
              }}
              pick={pick}
              ready={otherReady}
              onCamera={camera}
            />
            <div className="spindle-comparison-caption">
              <span>
                {otherRun.condition} · seed {otherRun.seed}
              </span>
              <strong>
                {otherRun.frames[otherFrame].poles.length} centrosomes
              </strong>
              <span>
                {otherRun.frames[otherFrame].time.toFixed(2)} s · saved physical
                time
              </span>
            </div>
          </div>
        )}
        <div className="spindle-badge">
          {bundle.category === "illustration"
            ? "Illustrative trajectory"
            : "Provisional simulation"}{" "}
          · {bundle.dimensionality}D
        </div>
        <div className="spindle-scale">
          Cell semiaxes {bundle.radius.join(" × ")} µm
          <br />
          Pearl: centrosomes · Cyan: filaments
          {recipe.trails ? " · Amber: pole tracks" : ""}
        </div>
        <div className="spindle-caption">
          <span>
            {run.condition} · seed {run.seed}
          </span>
          <strong>{frame.poles.length} centrosomes</strong>
          <span>{frame.time.toFixed(2)} s · saved physical time</span>
        </div>
      </div>
      <div className="spindle-toolbar">
        <label>
          Condition
          <select
            aria-label="Condition"
            value={recipe.run}
            onChange={(e) => {
              const i = Number(e.target.value),
                t = frame.time;
              let nearest = 0;
              bundle.runs[i].frames.forEach((f, j) => {
                if (
                  Math.abs(f.time - t) <
                  Math.abs(bundle.runs[i].frames[nearest].time - t)
                )
                  nearest = j;
              });
              patch({ run: i, frame: nearest });
            }}
          >
            {bundle.runs.map((r, i) => (
              <option key={i} value={i}>
                {r.condition} · seed {r.seed}
              </option>
            ))}
          </select>
        </label>
        <label>
          Compare with
          <select
            aria-label="Comparison"
            value={recipe.compare ?? ""}
            onChange={(e) =>
              patch({
                compare: e.target.value === "" ? null : Number(e.target.value),
                camera: null,
              })
            }
          >
            <option value="">Single trajectory</option>
            {bundle.runs.map((r, i) => (
              <option key={i} value={i}>
                {r.condition} · seed {r.seed}
              </option>
            ))}
          </select>
        </label>
        <label>
          View
          <select
            aria-label="View"
            value={recipe.shot}
            onChange={(e) =>
              patch({
                shot: e.target.value as SpindleRecipe["shot"],
                camera: undefined,
              })
            }
          >
            <option value="front">Front</option>
            <option value="oblique">Oblique</option>
            <option value="detail">Aster detail</option>
          </select>
        </label>
        <label>
          Filaments
          <select
            aria-label="Filaments"
            value={recipe.treatment}
            onChange={(e) =>
              patch({ treatment: e.target.value as SpindleRecipe["treatment"] })
            }
          >
            <option value="luminous">Luminous</option>
            <option value="fine">Fine</option>
          </select>
        </label>
        <label>
          Centrosome
          <select
            aria-label="Centrosome"
            value={recipe.selected || ""}
            onChange={(e) => patch({ selected: e.target.value || null })}
          >
            <option value="">All asters</option>
            {frame.poles.map((p) => (
              <option key={p.id}>{p.id}</option>
            ))}
          </select>
        </label>
        <button
          onClick={() => patch({ trails: !recipe.trails })}
          aria-pressed={recipe.trails}
        >
          Trails
        </button>
        <button onClick={download} disabled={readyRevision !== recipe.revision}>
          Save image
        </button>
      </div>
      <label className="spindle-time">
        Physical time · {frame.time.toFixed(2)} s
        <input
          aria-label="Spindle physical time"
          type="range"
          min={0}
          max={run.frames.length - 1}
          value={recipe.frame}
          onChange={(e) => patch({ frame: Number(e.target.value) })}
        />
        <span>
          0 s<span>{run.frames.at(-1)!.time} s</span>
        </span>
      </label>
      {selected && (
        <p className="spindle-readout">
          {selected.id} · (
          {selected.position.map((v) => v.toFixed(3)).join(", ")}) µm · nearest
          centrosome{" "}
          {Math.min(
            ...frame.poles
              .filter((p) => p.id !== selected.id)
              .map((p) =>
                Math.hypot(
                  ...p.position.map((v, i) => v - selected.position[i]),
                ),
              ),
          ).toFixed(3)}{" "}
          µm
        </p>
      )}
      <details>
        <summary>Trajectory & presentation</summary>
        <p>
          {bundle.model_id}. Positions use µm; time uses seconds. Lighting,
          cortex, filament display width and colors are illustrative. Frames are
          sampled without interpolation. Camera stays fixed as poles move.
          Simulation seeds are not biological samples.
        </p>
        <pre>{JSON.stringify(recipe, null, 2)}</pre>
      </details>
    </section>
  );
}
