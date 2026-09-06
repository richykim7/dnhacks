import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "./ui/button";
import { AnimatedTabs } from "./ui/animated-tabs";
import { ErrorNotice, Loading } from "./common";
import type { JsonRecord } from "@/lib/types";

const Workbench = lazy(() => import("./InhibitorWorkbench"));

const views = new Map<
  string,
  { view: number[]; representation: string; chain: string; residue: string }
>();
export default function Structures({
  artifact,
  url,
  owner,
}: {
  artifact: JsonRecord;
  url: string;
  owner: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const host = useRef<HTMLDivElement>(null),
    viewer = useRef<any>(null);
  const saved = views.get(artifact.artifact_id);
  const [representation, setRepresentation] = useState(
    saved?.representation || "cartoon",
  );
  const [chain, setChain] = useState(saved?.chain || ""),
    [residue, setResidue] = useState(saved?.residue || "");
  const [chains, setChains] = useState<string[]>([]);
  const [rotate, setRotate] = useState(false);
  const [busy, setBusy] = useState(true),
    [error, setError] = useState("");
  const [theme, setTheme] = useState(document.documentElement.dataset.theme);
  const options = useRef({ representation, chain, residue });
  options.current = { representation, chain, residue };
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setTheme(document.documentElement.dataset.theme),
    );
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    let v: any;
    const observer = new ResizeObserver(() => v?.resize());
    const element = host.current;
    if (element) observer.observe(element);
    setBusy(true);
    setError("");
    async function open() {
      const response = await fetch(url, { signal: abort.signal });
      if (!response.ok)
        throw new Error("This experiment artifact is unavailable.");
      const raw = await response.arrayBuffer();
      if (raw.byteLength > 20 * 1024 * 1024)
        throw new Error("Structure exceeds the 20 MB viewer limit.");
      const text = new TextDecoder().decode(raw);
      if (artifact.format === "pdb" && !/^(ATOM  |HETATM)/m.test(text))
        throw new Error("No atoms could be read from this structure.");
      const m = await import("3dmol");
      if (abort.signal.aborted || !element) return;
      v = m.createViewer(element, {
        antialias: true,
        upscale: true,
        cartoonQuality: 8,
        backgroundColor:
          document.documentElement.dataset.theme === "dark"
            ? "#111819"
            : "#edf1ed",
        ambientOcclusion: { strength: 0.65, radius: 4 },
        orthographic: true,
      });
      viewer.current = v;
      const model = v.addModel(text, artifact.format);
      const atoms = model.selectedAtoms({});
      if (!atoms.length || atoms.length > 100000)
        throw new Error(
          "Structure contains no atoms or exceeds the viewer limit.",
        );
      setChains([...new Set<string>(atoms.map((a: any) => a.chain || ""))]);
      v.zoomTo();
      v.zoom(1.3);
      const previous = views.get(artifact.artifact_id);
      if (previous?.view) v.setView(previous.view);
      v.setViewChangeCallback(() => {
        views.set(artifact.artifact_id, {
          view: v.getView(),
          ...options.current,
        });
        if (views.size > 24) views.delete(views.keys().next().value!);
      });
      setBusy(false);
    }
    void open().catch((e) => {
      if (!abort.signal.aborted) {
        setError(e.message);
        setBusy(false);
      }
    });
    return () => {
      abort.abort();
      observer.disconnect();
      if (v) {
        views.set(artifact.artifact_id, {
          view: v.getView(),
          ...options.current,
        });
        v.spin(false);
        v.clear();
      }
      viewer.current = null;
      element?.replaceChildren();
    };
  }, [artifact.artifact_id, url]);
  useEffect(() => {
    const v = viewer.current;
    if (!v || busy || error) return;
    let disposed = false;
    const selection = chain ? { chain } : {};
    v.setBackgroundColor(theme === "dark" ? "#111819" : "#edf1ed");
    v.removeAllSurfaces();
    v.removeAllLabels();
    v.setStyle({}, {});
    v.setStyle(
      selection,
      representation === "sticks"
        ? { stick: { colorscheme: "Jmol", radius: 0.16 } }
        : {
            cartoon: {
              color: theme === "dark" ? "#a8ccbd" : "#527f70",
              thickness: 0.45,
              arrows: true,
            },
          },
    );
    if (representation === "cartoon")
      v.addStyle(
        { ...selection, hetflag: true, not: { resn: "HOH" } },
        { stick: { colorscheme: "Jmol", radius: 0.18 } },
      );
    if (representation === "surface")
      void v
        .addSurface(
          1,
          { opacity: 0.85, color: theme === "dark" ? "#91bcb2" : "#6d9989" },
          selection,
        )
        .then(() => {
          if (!disposed) v.render();
        });
    if (residue && /^-?\d+$/.test(residue))
      v.addStyle(
        { ...selection, resi: Number(residue) },
        {
          stick: { color: "#dcac70", radius: 0.26 },
          sphere: { color: "#dcac70", scale: 0.25 },
        },
      );
    v.spin(
      rotate && !matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "y"
        : false,
      0.25,
    );
    v.render();
    return () => {
      disposed = true;
      v.spin(false);
    };
  }, [representation, chain, residue, rotate, busy, error, theme]);
  return (
    <section
      className="artifact-viewer"
      aria-label={`Experiment structure ${artifact.name}`}
    >
      <Button className="pocket-open" onClick={() => setExpanded(true)}>Open inhibitor workbench</Button>
      {expanded && <Suspense fallback={<Loading label="Opening pocket observatory" />}><Workbench artifact={artifact} owner={owner} url={url.replace('/blob/', '/geometry/')} onClose={() => setExpanded(false)} /></Suspense>}
      <div className="structure-toolbar">
        <AnimatedTabs
          label="Molecular representation"
          value={representation}
          onChange={setRepresentation}
          tabs={[
            { value: "cartoon", label: "Ribbon" },
            { value: "sticks", label: "Atomic" },
            { value: "surface", label: "Surface" },
          ]}
        />
        <Button
          variant="ghost"
          size="icon"
          aria-label="Reset structure view"
          onClick={() => {
            viewer.current?.zoomTo();
            viewer.current?.render();
          }}
        >
          <RotateCcw size={15} />
        </Button>
      </div>
      <ErrorNotice message={error} />
      <div
        className="artifact-canvas"
        ref={host}
        aria-label={`Interactive molecular structure ${artifact.name}`}
      />
      {busy && <Loading label="Preparing experiment structure" />}
      <div className="artifact-controls">
        <label>
          Chain
          <select value={chain} onChange={(e) => setChain(e.target.value)}>
            <option value="">All chains</option>
            {chains.filter(Boolean).map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Residue
          <input
            type="number"
            value={residue}
            placeholder="Number"
            onChange={(e) => setResidue(e.target.value)}
          />
        </label>
        <label className="check-label">
          <input
            type="checkbox"
            checked={rotate}
            onChange={(e) => setRotate(e.target.checked)}
          />
          Slow rotation
        </label>
      </div>
      <p className="muted">
        {artifact.atom_count?.toLocaleString()} atoms · Drag to rotate, scroll
        to zoom. Colours are decorative, not confidence.
      </p>
    </section>
  );
}
