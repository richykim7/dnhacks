import { useCallback, useEffect, useRef, useState } from "react";
import Stage, { type StageHandle } from "./Stage";
import { type Bundle, type Preset, type SceneState, label } from "./types";
import "./binder.css";

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
async function sha(text: string) {
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)),
    ),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}
export default function Workbench({
  url,
  sha256,
}: {
  url: string;
  sha256: string;
}) {
  const [bundle, setBundle] = useState<Bundle | null>(null),
    [error, setError] = useState("");
  const [state, setState] = useState<SceneState>({
    preset: "hero",
    style: "pearl",
    selected: null,
    revision: 0,
  });
  const handle = useRef<StageHandle | null>(null),
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
      const text = await r.text();
      if (text.length > 20 * 1024 * 1024 || (await sha(text)) !== sha256)
        throw Error("Candidate artifact hash mismatch.");
      const b = JSON.parse(text) as Bundle;
      if (b.schema !== "binder_bundle.v1" || !b.structure.atoms.length)
        throw Error("Unsupported binder bundle.");
      if (!controller.signal.aborted) setBundle(b);
    })().catch((e) => {
      if (!controller.signal.aborted) setError(String(e.message));
    });
    return () => controller.abort();
  }, [url, sha256]);
  const onHandle = useCallback((h: StageHandle) => {
    handle.current = h;
    h.ready().then(() => setLoaded(true));
  }, []);
  const onPick = useCallback(
    (id: string) => setState((s) => ({ ...s, selected: id })),
    [],
  );
  useEffect(() => {
    if (
      !import.meta.env.DEV ||
      !new URLSearchParams(location.search).has("sceneReview")
    )
      return;
    const w = window as unknown as { sceneReview?: unknown };
    const bridge = {
      apply: async (patch: Partial<SceneState>) => {
        if (patch.preset && !presets.includes(patch.preset))
          throw Error("Unknown preset");
        setLoaded(false);
        setState((s) => ({ ...s, ...patch, revision: s.revision + 1 }));
        await new Promise((r) =>
          requestAnimationFrame(() => requestAnimationFrame(r)),
        );
      },
      ready: async () => {
        const deadline = performance.now() + 30000;
        while (!handle.current) {
          if (performance.now() > deadline)
            throw Error("Scene initialization timed out");
          await new Promise(requestAnimationFrame);
        }
        await handle.current.ready();
      },
      inspect: () => ({
        ...handle.current?.inspect(),
        ...stateRef.current,
        bundle_sha256: sha256,
      }),
      pick: (x: number, y: number) => {
        const id = handle.current?.pick(x, y);
        if (id) onPick(id);
        return id;
      },
      capture: () => handle.current?.capture(),
    };
    w.sceneReview = bridge;
    return () => {
      if (w.sceneReview === bridge) delete w.sceneReview;
    };
  }, [sha256, onPick, bundle]);
  if (error) return <p role="alert">{error}</p>;
  if (!bundle) return <p role="status">Opening candidate coordinates…</p>;
  const residues = new Map(bundle.structure.residues.map((r) => [r.id, r]));
  const contacts = bundle.metrics.contacts.filter(
    (c) => c.distance_angstrom <= 4.5,
  );
  const ids = [
    ...new Set(contacts.flatMap((c) => [c.target_residue, c.binder_residue])),
  ];
  const selected = state.selected ? residues.get(state.selected) : null;
  const rows = state.selected
    ? contacts.filter(
        (c) =>
          c.target_residue === state.selected ||
          c.binder_residue === state.selected,
      )
    : contacts;
  return (
    <section
      className={`binder-workbench ${expanded ? "binder-expanded" : ""}`}
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
      <div className="binder-layout">
        <div className="binder-specimen">
          <div
            className="binder-stage"
            data-testid="binder-stage"
            aria-label="Interactive target and binder; exact contacts in table below"
          >
            <Stage
              bundle={bundle}
              state={state}
              onHandle={onHandle}
              onPick={onPick}
            />
            <div className="binder-caption">
              <span className="binder-badge">
                {bundle.manifest.provenance.category.replaceAll("_", " ")}
              </span>
              <strong>{bundle.manifest.candidate_id}</strong>
              <small>
                {state.preset === "exploded"
                  ? "Illustrative separation · measurements use original pose"
                  : ["interface-close", "reverse"].includes(state.preset)
                    ? "Contact-only cutaway · reduced sphere radii · Å"
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
                  onClick={() =>
                    setState((s) => ({
                      ...s,
                      preset: p,
                      revision: s.revision + 1,
                    }))
                  }
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
                aria-pressed={state.selected === id}
                onClick={() => onPick(id)}
              >
                {label(residues.get(id)!)}
              </button>
            ))}
          </div>
        </div>
        <aside className="binder-inspector">
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
              <dd>{bundle.metrics.counts["4.5"]}</dd>
            </div>
            <div>
              <dt>Total buried area</dt>
              <dd>
                {bundle.metrics.total_buried_area_angstrom2?.toFixed(0) ??
                  "Not measured"}{" "}
                Å²
              </dd>
            </div>
            <div>
              <dt>Pairs below 2.0 Å</dt>
              <dd>{bundle.metrics.clash_count}</dd>
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
            Material study
            <select
              value={state.style}
              onChange={(e) =>
                setState((s) => ({
                  ...s,
                  style: e.target.value as "pearl" | "copper",
                }))
              }
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
                    ...handle.current?.inspect(),
                    ...state,
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
      {state.preset === "candidate-compare" && (
        <p className="binder-context">
          Comparison needs a second collected candidate evaluated with the same
          protocol. No second candidate is present in this bundle.
        </p>
      )}
      <details className="binder-table" open={Boolean(selected)}>
        <summary>Exact contacts · {rows.length} atom pairs</summary>
        <p>
          Interchain heavy-atom distance rule v1. Sensitivity:{" "}
          {bundle.metrics.counts["4.0"]} pairs at 4.0 Å;{" "}
          {bundle.metrics.counts["5.0"]} at 5.0 Å. Buried area: SASA(target) +
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
                      bundle.structure.atoms.find((a) => a.id === c.target_atom)
                        ?.name
                    }
                  </td>
                  <td>
                    {label(residues.get(c.binder_residue)!)} /{" "}
                    {
                      bundle.structure.atoms.find((a) => a.id === c.binder_atom)
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
