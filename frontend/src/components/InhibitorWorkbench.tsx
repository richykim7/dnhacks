/// <reference types="vite/client" />
import {
  Component,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, Download } from "lucide-react";
import type { JsonRecord } from "@/lib/types";
import {
  center,
  validateGeometry,
  poseGeometry,
  type Bundle,
  type Geometry,
  type Recipe,
  type Vec3,
} from "@/lib/inhibitor";
import InhibitorScene from "./InhibitorScene";
import "../inhibitor.css";

type Review = {
  ready: () => Promise<number>;
  setCamera: (shot: Recipe["shot"]) => void;
  setStyle: (s: Recipe["style"]) => void;
  setFrame: (f: number) => void;
  select: (ids: string[]) => void;
  loadFixture: (hash: string) => void;
  capture: (revision: number) => Promise<{ png: string; recipe: Recipe }>;
};
declare global {
  interface Window {
    sceneReview?: Review;
    inhibitorScene?: {
      ready: () => Promise<number>;
      recipe: () => Recipe | null;
    };
  }
}
class SceneBoundary extends Component<
  { children: ReactNode },
  { error: boolean }
> {
  state = { error: false };
  static getDerivedStateFromError() {
    return { error: true };
  }
  render() {
    return this.state.error ? (
      <p role="alert">
        Renderer unavailable. Return to the experiment to inspect the reference
        structure.
      </p>
    ) : (
      this.props.children
    );
  }
}
function save(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function InhibitorWorkbench({
  artifact,
  url,
  owner,
  experimentId,
  onClose,
}: {
  artifact: JsonRecord;
  url: string;
  owner: string;
  experimentId: string;
  onClose: () => void;
}) {
  const [g, setG] = useState<Geometry | null>(null),
    [error, setError] = useState(""),
    [recipe, setRecipe] = useState<Recipe | null>(null);
  const [state, setState] = useState<JsonRecord>({
      jobs: [],
      bundles: [],
      scenes: [],
    }),
    [bundle, setBundle] = useState<Bundle | null>(null),
    [loadedBundle, setLoadedBundle] = useState<string | null>(null);
  const [query, setQuery] = useState(""),
    [tab, setTab] = useState("contacts"),
    [measurement, setMeasurement] = useState<JsonRecord | null>(null),
    [contacts, setContacts] = useState<JsonRecord | null>(null);
  const [mode, setMode] = useState<"explore" | "follow" | "replay">("explore"),
    [cursor, setCursor] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1);
  const [spec, setSpec] = useState(""),
    [busy, setBusy] = useState(false);
  const latest = useRef(recipe);
  latest.current = recipe;
  const secondary = useRef(-1),
    rendered = useRef(-1),
    canvas = useRef<HTMLCanvasElement | null>(null),
    revision = useRef(0);
  const base = useMemo(() => {
    const u = new URL(url, location.origin);
    u.pathname = u.pathname.replace(
      /\/geometry\/[^/]+$/,
      `/inhibitor/${encodeURIComponent(experimentId)}`,
    );
    return u;
  }, [url, experimentId]);
  const get = useCallback(async (u: URL) => {
    const r = await fetch(u);
    const data = await r.json();
    if (!r.ok) throw Error(data.error || "Workbench request failed");
    return data;
  }, []);
  const refresh = useCallback(async () => {
    const u = new URL(base);
    u.searchParams.set(
      "source_hash",
      String(artifact.sha256 || artifact.storage_key),
    );
    setState(await get(u));
  }, [base, get, artifact.sha256, artifact.storage_key]);
  const call = useCallback(
    async (args: JsonRecord) => {
      const r = await fetch(base, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_hash: artifact.sha256 || artifact.storage_key,
          ...args,
        }),
      });
      const v = await r.json();
      if (!r.ok) throw Error(v.error || "Operation failed");
      await refresh();
      return v;
    },
    [base, artifact, refresh],
  );
  useEffect(() => {
    let active = true;
    get(new URL(url, location.origin))
      .then((data) => {
        if (!active) return;
        const geo = validateGeometry(data, artifact.sha256);
        setG(geo);
        const ligand = geo.residues
          .filter((r) => r.kind === "ligand")
          .sort((a, b) => b.atoms.length - a.atoms.length)[0];
        setRecipe({
          schema_version: 1,
          source_hash: geo.source_hash,
          revision: 0,
          style: "matte",
          shot: "pocket",
          ligand: ligand?.id || "",
          model: ligand?.model || 0,
          clip: false,
          selected: [],
          frame: 0,
          pose: "reference",
          compare: false,
          prepared: false,
        });
        setSpec(
          JSON.stringify(
            {
              spec_version: 1,
              chain: ligand?.chain || "A",
              ligand_sequence: ligand?.sequence || "",
              ligand_name: ligand?.name || "",
              assembly: "deposited-chain",
              protonation: "meeko-standard-templates",
              repair_policy: "reject",
              water_policy: "exclude",
              cofactor_policy: "reject",
              exclude_additives: [],
              altloc: "A",
              margin_angstrom: 5,
              seeds: [17, 29, 41],
              exhaustiveness: 8,
              pose_count: 5,
              timeout_s: 600,
              rationale:
                "Describe why this preparation is appropriate before running",
            },
            null,
            2,
          ),
        );
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [get, url, artifact.sha256]);
  useEffect(() => {
    void refresh().catch((e) => setError(e.message));
    if (base.searchParams.has("through")) return;
    const timer = setInterval(
      () => void refresh().catch((e) => setError(e.message)),
      1500,
    );
    return () => clearInterval(timer);
  }, [refresh, base]);
  const actionsJson = JSON.stringify(state.scenes);
  const actions = useMemo(
    () => JSON.parse(actionsJson) as JsonRecord[],
    [actionsJson],
  );
  const agents = useMemo(
    () => actions.filter((s) => s.actor === "agent"),
    [actions],
  );
  const patch = useCallback((p: Partial<Recipe>) => {
    setMode("explore");
    setPlaying(false);
    rendered.current = -1;
    setRecipe((r) => (r ? { ...r, ...p, revision: ++revision.current } : r));
  }, []);
  const applyRecorded = useCallback((r: Recipe) => {
    if (JSON.stringify(latest.current) === JSON.stringify(r)) return;
    rendered.current = -1;
    revision.current = Math.max(revision.current, r.revision);
    setRecipe(structuredClone(r));
  }, []);
  useEffect(() => {
    if (g && mode === "follow" && agents.length)
      applyRecorded(agents[agents.length - 1].recipe);
  }, [g, mode, agents, applyRecorded]);
  useEffect(() => {
    if (g && mode === "replay" && agents[cursor])
      applyRecorded(agents[cursor].recipe);
  }, [g, mode, cursor, agents, applyRecorded]);
  useEffect(() => {
    if (!playing || mode !== "replay" || cursor >= agents.length - 1) {
      if (cursor >= agents.length - 1) setPlaying(false);
      return;
    }
    const delay =
      Math.max(
        100,
        Math.min(
          30000,
          (agents[cursor + 1].recorded_at - agents[cursor].recorded_at) * 1000,
        ),
      ) / speed;
    const t = setTimeout(() => setCursor((c) => c + 1), delay);
    return () => clearTimeout(t);
  }, [playing, mode, cursor, speed, agents]);
  const pinned = new URLSearchParams(location.search).has("sceneRevision");
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const requested = q.get("sceneRevision");
    if (!g || requested === null) return;
    const action = actions.find(
      (s) =>
        s.actor === (q.get("sceneActor") || "agent") &&
        s.recipe.revision === Number(requested),
    );
    if (action) {
      applyRecorded(action.recipe);
      if (action.actor === "agent") {
        setMode("replay");
        setCursor(agents.findIndex((s) => s.sequence === action.sequence));
      }
    }
  }, [g, actions, agents, applyRecorded]);
  const activeBundle =
    recipe?.bundle ||
    (!pinned && mode === "explore"
      ? state.bundles.at(-1)?.storage_key
      : undefined);
  useEffect(() => {
    if (!activeBundle) {
      setBundle(null);
      return;
    }
    let live = true;
    const u = new URL(base);
    u.searchParams.set("bundle", activeBundle);
    get(u)
      .then((v) => {
        if (live) {
          setBundle(v);
          setLoadedBundle(activeBundle);
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [activeBundle, base, get]);
  const posed = useMemo(
    () =>
      g && recipe
        ? poseGeometry(
            recipe.bundle && bundle && !recipe.prepared
              ? bundle.docking_geometry
              : g,
            bundle,
            recipe.prepared ? {...recipe,pose:'reference'} : recipe,
          )
        : g,
    [g, bundle, recipe],
  );
  const viewRecipe = useMemo(() => {
    if (!g || !recipe || recipe.camera) return recipe;
    const atoms = g.atoms.filter((a) => a.model === recipe.model),
      ligand = atoms.filter((a) => a.residue_id === recipe.ligand);
    const target = center(
      recipe.shot === "arrival" ? atoms : ligand.length ? ligand : atoms,
    );
    const radius = Math.max(
      10,
      ...atoms.map((a) =>
        Math.hypot(...a.position.map((v, i) => v - target[i])),
      ),
    );
    const dist = recipe.shot === "arrival" ? radius * 2.8 : 25;
    const offset =
      recipe.shot === "oblique" ? [0.85, 0.38, 0.9] : [0.2, 0.22, 1.3];
    return {
      ...recipe,
      camera: {
        target,
        position: target.map((v, i) => v + offset[i] * dist) as Vec3,
      },
    };
  }, [g, recipe]);
  const comparison = useMemo(() => {
    if (!g || !recipe) return g;
    if (recipe.prepared && bundle) return poseGeometry(bundle.docking_geometry,bundle,{...recipe,pose:'reference'});
    return poseGeometry(g, bundle, { ...recipe, pose: "reference" });
  }, [g, bundle, recipe]);
  useEffect(() => {
    if (!recipe?.ligand) return;
    if (bundle) {
      setContacts(bundle.contacts?.[recipe.pose || "reference"] || null);
      return;
    }
    let live = true;
    const u = new URL(url, location.origin);
    u.searchParams.set("operation", "contacts");
    u.searchParams.set("residue", recipe.ligand);
    get(u)
      .then((v) => live && setContacts(v))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [url, get, recipe?.ligand, recipe?.pose, bundle]);
  const ack = useCallback((rev: number, el: HTMLCanvasElement) => {
    if (latest.current?.revision === rev) {
      rendered.current = rev;
      canvas.current = el;
    }
  }, []);
  const onCamera = useCallback(
    (position: Vec3, target: Vec3) => {
      setMode("explore");
      setPlaying(false);
      patch({ camera: { position, target } });
    },
    [patch],
  );
  const pick = useCallback(
    (id: string) => {
      setMode("explore");
      patch({
        selected: latest.current?.selected.includes(id)
          ? latest.current.selected.filter((i) => i !== id)
          : [...(latest.current?.selected || []).slice(-2), id],
      });
      setMeasurement(null);
    },
    [patch],
  );
  const ready = useCallback(async () => {
    await document.fonts.ready;
    const expected = latest.current?.revision;
    const start = performance.now();
    while (
      rendered.current !== expected ||
      (latest.current?.compare && secondary.current !== expected) ||
      !canvas.current
    ) {
      if (latest.current?.revision !== expected)
        throw Error("Scene changed while waiting");
      if (performance.now() - start > 20000)
        throw Error("Scene did not render");
      await new Promise(requestAnimationFrame);
    }
    return expected!;
  }, []);
  const capture = useCallback(
    async (expected: number) => {
      if (expected !== latest.current?.revision)
        throw Error("Stale capture revision");
      await ready();
      if (expected !== latest.current?.revision)
        throw Error("Stale capture revision");
      return {
        png: canvas.current!.toDataURL("image/png"),
        recipe: structuredClone(latest.current!),
      };
    },
    [ready],
  );
  useEffect(() => {
    window.inhibitorScene = { ready, recipe: () => latest.current };
    return () => {
      delete window.inhibitorScene;
    };
  }, [ready]);
  useEffect(() => {
    if (
      !import.meta.env.DEV ||
      new URLSearchParams(location.search).get("sceneReview") !== "1" ||
      !g
    )
      return;
    window.sceneReview = {
      ready,
      capture,
      setCamera: (shot) => patch({ shot, camera: undefined }),
      setStyle: (style) => patch({ style }),
      setFrame: (f) => {
        if (f !== 0) throw Error("No recorded dynamics");
      },
      select: (ids) => {
        if (ids.some((i) => !g.atoms.some((a) => a.id === i)))
          throw Error("Unknown atom");
        patch({ selected: ids });
      },
      loadFixture: (hash) => {
        if (hash !== g.source_hash) throw Error("Fixture mismatch");
        patch({ shot: "arrival" });
      },
    };
    return () => {
      delete window.sceneReview;
    };
  }, [g, ready, capture, patch]);
  useEffect(() => {
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = old;
      document.removeEventListener("keydown", key);
    };
  }, [onClose]);
  async function execute(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const measure = () =>
    execute(async () => {
      const value = await call({
        operation: "measure",
        atom_ids: recipe!.selected,
        bundle: activeBundle,
        pose: recipe!.pose || "reference",
      });
      setMeasurement(value);
    });
  const exportPlate = () =>
    execute(async () => {
      let captureReceipt: JsonRecord | undefined;
      if (!readonly) {
        const own = state.scenes.filter((s: JsonRecord) => s.actor === "user");
        const {
          revision: _,
          source_hash: __,
          schema_version: ___,
          ...fields
        } = viewRecipe!;
        const saved = await call({
          operation: "set_scene_view",
          expected_revision: own.at(-1)?.recipe.revision || 0,
          patch: fields,
          note: "User exported an evidence plate",
        });
        captureReceipt = await call({
          operation: "capture_scene",
          expected_revision: saved.recipe.revision,
          viewport: [1600, 1000],
        });
        const u = new URL(base);
        u.searchParams.set("file", String(captureReceipt!.image_hash));
        const a = document.createElement("a");
        a.href = u.toString();
        a.download = "inhibitor-evidence-plate.png";
        a.click();
      } else {
        const result = await capture(recipe!.revision);
        const a = document.createElement("a");
        a.href = result.png;
        a.download = "inhibitor-playback-canvas.png";
        a.click();
      }
      save(
        "inhibitor-report.json",
        JSON.stringify(
          {
            owner,
            provenance: artifact.provenance,
            scene: viewRecipe,
            capture: captureReceipt,
            report: bundle?.report,
            preparation: bundle?.preparation,
            contacts,
            measurement,
          },
          null,
          2,
        ),
        "application/json",
      );
    });
  const ligand = g?.residues.find((r) => r.id === recipe?.ligand),
    pose = [...(bundle?.poses || []), ...(bundle?.controls || [])].find(
      (p) => p.id === recipe?.pose,
    );
  const readonly = base.searchParams.has("through");
  return createPortal(
    <div
      className="pocket-workbench"
      role="dialog"
      aria-modal="true"
      aria-label="Inhibitor workbench"
    >
      <header className="pocket-header">
        <button autoFocus onClick={onClose}>
          <ArrowLeft size={16} /> Return to experiment
        </button>
        <span className="pocket-owner">{owner}</span>
        <span className="pocket-reference">
          {String(artifact.provenance?.category || "reference").replaceAll(
            "_",
            " ",
          )}
        </span>
      </header>
      <div className="pocket-title">
        <div>
          <p className="pocket-eyebrow">MOLECULAR INSTRUMENTS / 01</p>
          <h1>
            The pocket observatory<span>.</span>
          </h1>
          <p>Prepare · dock · compare · verify the geometry.</p>
        </div>
        <button disabled={!recipe} onClick={() => void exportPlate()}>
          <Download size={16} /> Evidence plate
        </button>
      </div>
      {error && (
        <div role="alert" className="pocket-error">
          {error}
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      <section className="pocket-timeline" aria-label="Agent scene timeline">
        <label>
          Interaction mode
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as typeof mode);
              setPlaying(false);
            }}
          >
            <option value="explore">Explore myself</option>
            <option value="follow">Watch agent live</option>
            <option value="replay">Replay agent actions</option>
          </select>
        </label>
        <button
          disabled={!agents.length}
          onClick={() => {
            setMode("replay");
            if (cursor >= agents.length - 1) setCursor(0);
            setPlaying((p) => !p);
          }}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <input
          aria-label="Agent scene action"
          type="range"
          min="0"
          max={Math.max(0, agents.length - 1)}
          value={cursor}
          disabled={!agents.length}
          onChange={(e) => {
            setMode("replay");
            setCursor(Number(e.target.value));
            setPlaying(false);
          }}
        />
        <label>
          Speed
          <select
            aria-label="Playback speed"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          >
            {[0.5, 1, 2, 4, 8].map((s) => (
              <option key={s} value={s}>
                {s}×
              </option>
            ))}
          </select>
        </label>
        <span>
          {agents.length
            ? `${cursor + 1}/${agents.length} · ${agents[cursor]?.note || "Scene action"}`
            : "No agent scene actions recorded yet"}
        </span>
        <small>
          Action replay · no physical simulation time. Exploring preserves agent
          history.
        </small>
      </section>
      <div className="pocket-layout">
        <main className="pocket-stage">
          <div className="pocket-stage-meta">
            <span>{artifact.name}</span>
            <span>
              {mode === "explore"
                ? "Your exploration"
                : mode === "follow"
                  ? "Following agent"
                  : "Recorded agent view"}{" "}
              · Å
            </span>
          </div>
          {posed &&
          viewRecipe &&
          (!activeBundle || loadedBundle === activeBundle) ? (
            <SceneBoundary>
              <div
                className={`pocket-canvases ${viewRecipe.compare ? "paired" : ""}`}
              >
                <InhibitorScene
                  g={posed}
                  surface={bundle?.surface}
                  recipe={viewRecipe}
                  pick={pick}
                  ack={ack}
                  onCamera={onCamera}
                />
                {viewRecipe.compare && comparison && (
                  <InhibitorScene
                    g={comparison}
                    recipe={{ ...viewRecipe, pose: "reference" }}
                    pick={pick}
                    ack={(rev) => {
                      secondary.current = rev;
                    }}
                    onCamera={onCamera}
                  />
                )}
              </div>
            </SceneBoundary>
          ) : (
            <p className="pocket-loading">
              {error ? "Geometry unavailable" : "Loading canonical geometry…"}
            </p>
          )}
          <div className="pocket-scene-caption">
            <span className="pocket-amber-dot" />
            <strong>
              {ligand
                ? `${ligand.name} · ${ligand.chain} ${ligand.sequence}`
                : "No ligand selected"}
            </strong>
            <span>
              {pose?.label || pose?.id || "Deposited reference"}
              {pose?.score !== undefined
                ? ` · ${pose.score.toFixed(2)} kcal/mol`
                : ""}
              {recipe?.compare
                ? " · right: " +
                  (recipe.prepared
                    ? "prepared receptor"
                    : "deposited reference")
                : ""}
            </span>
          </div>
          <div className="pocket-camera-tools">
            {(["arrival", "pocket", "oblique"] as const).map((shot) => (
              <button
                key={shot}
                onClick={() => {
                  setMode("explore");
                  patch({ shot, camera: undefined });
                }}
              >
                {shot}
              </button>
            ))}
          </div>
        </main>
        <aside className="pocket-inspector">
          <p className="pocket-eyebrow">EXPERIMENT LENS</p>
          <h2>{ligand?.name || "Structure"}</h2>
          <p className="pocket-secondary">
            {g?.atoms.length.toLocaleString()} deposited atoms · exploratory
          </p>
          <div
            className="pocket-tabs"
            role="tablist"
            aria-label="Pocket inspector"
          >
            {["contacts", "preparation", "docking", "display"].map((t) => (
              <button
                role="tab"
                aria-selected={tab === t}
                key={t}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          {tab === "contacts" && (
            <>
              <div className="pocket-stat">
                <strong>{contacts?.contacts?.length ?? "—"}</strong>
                <span>
                  heavy-atom proximities
                  <br />
                  within 4 Å
                </span>
              </div>
              <p className="pocket-secondary">
                Proximity is not a hydrogen-bond assignment.
              </p>
              <div className="pocket-contact-list">
                {contacts?.contacts
                  ?.slice(0, 80)
                  .map((c: JsonRecord, i: number) => (
                    <button
                      key={i}
                      onClick={() => {
                        patch({ selected: c.atom_ids });
                        setMeasurement({
                          value: c.distance,
                          units: "Å",
                          atom_ids: c.atom_ids,
                        });
                      }}
                    >
                      <span>
                        {c.residue_id.split(":").slice(-2).join(" ")}{" "}
                        {c.kind === "severe_overlap" ? "CLASH" : ""}
                      </span>
                      <strong>{c.distance.toFixed(2)} Å</strong>
                    </button>
                  ))}
              </div>
            </>
          )}
          {tab === "preparation" && (
            <div className="pocket-audit">
              <h3>{bundle ? "Preparation audit" : "No prepared inputs yet"}</h3>
              <p>
                Policy explicitly controls water exclusion, additives, alternate
                atoms and missing-atom repair.
              </p>
              {bundle && (
                <>
                  <button
                    onClick={() => patch({ compare: true, prepared: true, pose:'reference', bundle:activeBundle })}
                  >
                    Compare deposited / prepared
                  </button>
                  <p>
                    {
                      bundle.preparation.atom_map.filter(
                        (a: JsonRecord) => a.change === "added",
                      ).length
                    }{" "}
                    added atoms; {bundle.preparation.changes.length} recorded
                    residue/alternate decisions.
                  </p>
                  <details>
                    <summary>Complete preparation delta</summary>
                    <pre>{JSON.stringify(bundle.preparation, null, 2)}</pre>
                  </details>
                </>
              )}
              <p>
                No dynamics trajectory attached. Camera/action replay is not
                molecular dynamics.
              </p>
            </div>
          )}
          {tab === "docking" && (
            <div className="pocket-audit">
              <label>
                Frozen preparation & docking protocol
                <textarea
                  aria-label="Docking protocol"
                  value={spec}
                  onChange={(e) => setSpec(e.target.value)}
                  rows={12}
                />
              </label>
              <button
                disabled={readonly || busy}
                onClick={() =>
                  void execute(() =>
                    call({
                      operation: "dock",
                      spec: JSON.parse(spec),
                      idempotency_key: crypto.randomUUID(),
                    }),
                  )
                }
              >
                Prepare and dock
              </button>
              <p>
                One CPU · declared wall-time cap. Review the protocol before
                execution; scores are not binding affinities.
              </p>
              {state.jobs.map((job: JsonRecord) => (
                <div key={job.job_id}>
                  <strong>{job.status}</strong>
                  <p>{job.error}</p>
                  {["running", "queued"].includes(job.status) && (
                    <button
                      onClick={() =>
                        void execute(() =>
                          call({ operation: "cancel", job_id: job.job_id }),
                        )
                      }
                    >
                      Cancel job
                    </button>
                  )}
                </div>
              ))}
              {bundle && (
                <>
                  <p>
                    Top-pose recovery:{" "}
                    {(100 * bundle.report.recovery.top_pose_fraction).toFixed(
                      0,
                    )}
                    % at ≤2 Å. Repeated seeds are not biological replicates.
                  </p>
                  <details>
                    <summary>Complete score table and controls</summary>
                    <pre>{JSON.stringify(bundle.report, null, 2)}</pre>
                  </details>
                  {Object.entries(bundle.files || {}).map(([name, key]) => (
                    <a
                      key={name}
                      href={`${base}${base.search ? "&" : "?"}file=${key}`}
                      download={name}
                    >
                      {name}{" "}
                    </a>
                  ))}
                </>
              )}
            </div>
          )}
          {tab === "display" && (
            <div className="pocket-audit">
              <label>
                Reference residue
                <select
                  value={recipe?.ligand || ""}
                  onChange={(e) =>
                    patch({
                      ligand: e.target.value,
                      selected: [],
                      camera: undefined,
                    })
                  }
                >
                  {g?.residues
                    .filter((r) => r.kind === "ligand")
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} {r.chain}:{r.sequence}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Treatment
                <select
                  aria-label="Render treatment"
                  value={recipe?.style}
                  onChange={(e) =>
                    patch({ style: e.target.value as Recipe["style"] })
                  }
                >
                  <option value="matte">Sculpted matte</option>
                  <option value="luminous">Luminous pocket</option>
                  <option value="measurement">Measurement</option>
                </select>
              </label>
              <label className="pocket-check">
                <input
                  type="checkbox"
                  checked={recipe?.clip || false}
                  onChange={(e) => patch({ clip: e.target.checked })}
                />{" "}
                Cutaway · display only
              </label>
              <label className="pocket-check">
                <input
                  type="checkbox"
                  checked={recipe?.compare || false}
                  onChange={(e) =>
                    patch({ compare: e.target.checked, prepared: false })
                  }
                />{" "}
                Synchronized comparison
              </label>
              <label className="pocket-check">
                <input
                  type="checkbox"
                  disabled={!bundle?.surface}
                  checked={recipe?.surface || false}
                  onChange={(e) => patch({ surface: e.target.checked })}
                />{" "}
                Approximate solvent-accessible pocket surface · probe 1.4 Å
              </label>
              <button
                onClick={() =>
                  save(
                    "scene.json",
                    JSON.stringify(recipe, null, 2),
                    "application/json",
                  )
                }
              >
                Save local camera bookmark
              </button>
              <button
                disabled={readonly || busy}
                onClick={() =>
                  void execute(() => {
                    const own = state.scenes.filter(
                      (s: JsonRecord) => s.actor === "user",
                    );
                    const {
                      revision: _,
                      source_hash: __,
                      schema_version: ___,
                      ...fields
                    } = recipe!;
                    return call({
                      operation: "set_scene_view",
                      expected_revision: own.at(-1)?.recipe.revision || 0,
                      patch: fields,
                      note: "User saved exploration bookmark",
                    });
                  })
                }
              >
                Record my bookmark
              </button>
            </div>
          )}
          <div className="pocket-measure">
            <label>
              Find atom/residue
              <input
                aria-label="Find an atom or residue"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="GLY, 604, N1"
              />
            </label>
            {query && (
              <div className="pocket-search-results">
                {posed?.atoms
                  .filter((a) =>
                    `${a.id} ${a.name}`
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .slice(0, 12)
                  .map((a) => (
                    <button key={a.id} onClick={() => pick(a.id)}>
                      {a.id}
                    </button>
                  ))}
              </div>
            )}
            <p>
              {recipe?.selected.length || 0} selected · two for distance, three
              for angle
            </p>
            <button
              disabled={
                readonly || !recipe || recipe.selected.length < 2 || busy
              }
              onClick={() => void measure()}
            >
              {activeBundle?'Measure prepared-receptor geometry':'Measure canonical geometry'}
            </button>
            {measurement && (
              <output>
                <strong>
                  {measurement.value.toFixed(3)} {measurement.units}
                </strong>
                <details>
                  <summary>Atom identities</summary>
                  {measurement.atom_ids.map((id: string) => (
                    <code key={id}>{id}</code>
                  ))}
                </details>
              </output>
            )}
          </div>
        </aside>
      </div>
      {bundle && (
        <section className="pocket-pose-rail" aria-label="Pose gallery">
          {[...bundle.controls, ...bundle.poses].map((p) => (
            <button
              aria-pressed={recipe?.pose === p.id}
              key={p.id}
              onClick={() => {
                setMode("explore");
                patch({
                  pose: p.id,
                  bundle: activeBundle,
                  ligand: bundle.ligand_residue,
                  selected: [],
                });
              }}
            >
              <strong>{p.label || p.id}</strong>
              <span>
                {p.score !== undefined
                  ? `${p.score.toFixed(2)} kcal/mol · ${p.rmsd?.toFixed(2)} Å RMSD`
                  : "Geometry control"}
              </span>
            </button>
          ))}
        </section>
      )}
      <footer className="pocket-footer">
        <span>
          Drag: orbit · scroll: zoom · right-drag: pan · click: select
        </span>
        <span>Affinity and cellular inhibition unmeasured.</span>
        <details>
          <summary>Source & limitations</summary>
          <p>{JSON.stringify(artifact.provenance)}</p>
          <p>SHA-256 {g?.source_hash}</p>
          {g?.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </details>
      </footer>
    </div>,
    document.body,
  );
}
