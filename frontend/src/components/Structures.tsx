import { useEffect, useRef, useState } from "react";
import { Box, Maximize, RotateCcw, Upload } from "lucide-react";
import { Button } from "./ui/button";
import { AnimatedTabs } from "./ui/animated-tabs";
import { Empty, ErrorNotice, Loading, Status } from "./common";

export default function Structures({
  theme,
  active = true,
}: {
  theme: string;
  active?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const viewer = useRef<any>(null);
  const [structure, setStructure] = useState<{
    text: string;
    format: string;
    name: string;
    source: string;
  } | null>(null);
  const [coloring, setColoring] = useState("uniform");
  const [pdb, setPdb] = useState("");
  const [representation, setRepresentation] = useState("cartoon");
  const [residue, setResidue] = useState("");
  const [rotate, setRotate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [atoms, setAtoms] = useState(0);
  const [residueMissing, setResidueMissing] = useState(false);
  const fetchAbort = useRef<AbortController | null>(null);
  useEffect(() => () => fetchAbort.current?.abort(), []);
  useEffect(() => {
    if (!structure || !host.current) return;
    let disposed = false;
    let v: any;
    setBusy(true);
    setError("");
    setAtoms(0);
    if (structure.format === "pdb" && !/^(ATOM  |HETATM)/m.test(structure.text)) {
      viewer.current?.spin(false);
      viewer.current?.clear();
      viewer.current?.render();
      setError(
        "No atoms could be read from this structure. Choose a valid PDB or mmCIF file.",
      );
      setBusy(false);
      return;
    }
    import("3dmol")
      .then((m) => {
        if (disposed || !host.current) return;
        v =
          viewer.current ||
          m.createViewer(host.current, {
            backgroundColor: theme === "dark" ? "#151a1b" : "#eef1ef",
            antialias: true,
          });
        viewer.current = v;
        v.spin(false);
        v.clear();
        const model = v.addModel(structure.text, structure.format);
        const count = model.selectedAtoms({}).length;
        if (!count)
          throw new Error(
            "No atoms could be read from this structure. Choose a valid PDB or mmCIF file.",
          );
        setAtoms(count);
        v.setStyle({}, { cartoon: { color: "#9fbfaf" } });
        v.zoomTo();
        v.render();
        setBusy(false);
      })
      .catch((e) => {
        if (!disposed) {
          setError((e as Error).message);
          setBusy(false);
        }
      });
    const observer = new ResizeObserver(() => v?.resize());
    observer.observe(host.current);
    return () => {
      disposed = true;
      observer.disconnect();
    };
  }, [structure]);
  useEffect(() => {
    const v = viewer.current;
    if (!v || busy) return;
    v.setBackgroundColor(theme === "dark" ? "#151a1b" : "#eef1ef");
    v.removeAllSurfaces();
    v.removeAllLabels();
    v.setStyle(
      {},
      representation === "sticks"
        ? { stick: { colorscheme: "Jmol", radius: 0.16 } }
        : {
            cartoon: {
              color: coloring === "sequence" ? "spectrum" : "#9fbfaf",
              opacity: representation === "surface" ? 0.45 : 1,
            },
          },
    );
    if (representation === "surface")
      void v.addSurface(1, {
        opacity: 0.72,
        color: theme === "dark" ? "#8abbb0" : "#487b70",
      });
    const exists =
      !residue ||
      v.getModel()?.selectedAtoms({ resi: Number(residue) }).length > 0;
    setResidueMissing(!exists);
    if (exists && residue && /^\d+$/.test(residue)) {
      v.setStyle(
        { resi: Number(residue) },
        {
          stick: { color: "#eab66c", radius: 0.3 },
          sphere: { color: "#eab66c", scale: 0.4 },
        },
      );
      v.addLabel(
        `Residue ${residue}`,
        { fontSize: 13, backgroundOpacity: 0.8 },
        { resi: Number(residue) },
      );
    }
    v.spin(
      active &&
        rotate &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "y"
        : false,
    );
    v.render();
    if (active) v.resize();
  }, [representation, residue, rotate, busy, theme, coloring, active]);
  async function loadPdb(value: string) {
    const code = value.trim().toUpperCase();
    if (!/^[0-9][A-Z0-9]{3}$/.test(code)) {
      setError("Enter a four-character PDB identifier, such as 1CRN.");
      return;
    }
    fetchAbort.current?.abort();
    const abort = new AbortController();
    fetchAbort.current = abort;
    const timeout = setTimeout(() => {
      abort.abort();
      setBusy(false);
      setError("The structure request timed out. Retry or open a local file.");
    }, 20000);
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`https://files.rcsb.org/download/${code}.pdb`, {
        signal: abort.signal,
      });
      if (!r.ok)
        throw new Error(
          `Could not retrieve ${code} from the Protein Data Bank (${r.status}).`,
        );
      const text = await r.text();
      setStructure({
        text,
        format: "pdb",
        name: code,
        source: `RCSB Protein Data Bank · ${code}`,
      });
      setPdb(code);
      setResidue("");
    } catch (e) {
      if (!abort.signal.aborted) {
        setError((e as Error).message);
        setBusy(false);
      }
    } finally {
      clearTimeout(timeout);
    }
  }
  return (
    <div className="structures-page">
      <header className="page-heading">
        <div>
          <div className="breadcrumb">Research workspace / Structures</div>
          <h1>Biology, in three dimensions</h1>
          <p>Inspect molecular geometry alongside your research.</p>
        </div>
        <Status label="Reference viewer" />
      </header>
      <div className="structure-layout">
        <aside className="structure-controls">
          <h2>Open a structure</h2>
          <p>
            Load an experimental structure from the Protein Data Bank, or
            inspect a local file.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void loadPdb(pdb);
            }}
          >
            <label>
              Protein Data Bank ID
              <input
                value={pdb}
                onChange={(e) => setPdb(e.target.value)}
                placeholder="e.g. 1CRN"
                maxLength={4}
              />
            </label>
            <Button type="submit" disabled={busy}>
              Load structure <Box size={15} />
            </Button>
          </form>
          <div className="or-divider">or</div>
          <label className="file-button">
            <Upload size={16} />
            Open PDB / mmCIF file
            <input
              type="file"
              accept=".pdb,.cif,.mmcif"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > 20 * 1024 * 1024) {
                  setError("Choose a structure smaller than 20 MB.");
                  return;
                }
                try {
                  fetchAbort.current?.abort();
                  setStructure({
                    text: await file.text(),
                    format: file.name.endsWith(".pdb") ? "pdb" : "cif",
                    name: file.name,
                    source: "Local file · stays in your browser",
                  });
                  setResidue("");
                } catch {
                  setError("The selected file could not be read.");
                }
              }}
            />
          </label>
          <div className="structure-provenance">
            <h3>Reference, not a prediction</h3>
            <p>
              This viewer displays the structure you load. The engine does not
              yet publish structure predictions, docking scores or
              variant-effect measurements.
            </p>
          </div>
          {structure && (
            <>
              <h3>Selected structure</h3>
              <p className="mono">{structure.name}</p>
              <small>{structure.source}</small>
              {atoms > 0 && <p>{atoms.toLocaleString()} atoms</p>}
              <label>
                Color by
                <select
                  value={coloring}
                  onChange={(e) => setColoring(e.target.value)}
                >
                  <option value="uniform">Uniform ribbon</option>
                  <option value="sequence">Position in sequence</option>
                </select>
              </label>
              <label>
                Highlight a residue
                <input
                  type="number"
                  min={1}
                  value={residue}
                  onChange={(e) => setResidue(e.target.value)}
                  placeholder="Residue number"
                />
              </label>
              {residueMissing && (
                <p className="notice">
                  That residue number is not present in this structure.
                </p>
              )}
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={rotate}
                  onChange={(e) => setRotate(e.target.checked)}
                />
                Slow rotation
              </label>
            </>
          )}
        </aside>
        <section className="structure-stage">
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
              size="icon"
              variant="ghost"
              aria-label="Reset structure view"
              onClick={() => {
                viewer.current?.zoomTo();
                viewer.current?.render();
              }}
            >
              <RotateCcw size={16} />
            </Button>
          </div>
          <ErrorNotice message={error} />
          {structure ? (
            <div
              className="molecule-view"
              ref={host}
              aria-label={`Interactive molecular structure ${structure.name}`}
            />
          ) : (
            <Empty
              title="Inspect a molecular structure"
              action={
                <Button onClick={() => void loadPdb("1CRN")}>
                  Explore crambin · 1CRN <Maximize size={14} />
                </Button>
              }
            >
              Open a protein to explore its fold, inspect a residue, and see the
              geometry behind a biological question.
            </Empty>
          )}
          {busy && (
            <div className="structure-loading">
              <Loading label="Preparing structure" />
            </div>
          )}
          <div className="structure-caption">
            {structure
              ? "Drag to rotate · Scroll to zoom · Right-drag to move"
              : "Interactive molecular structures · Powered by 3Dmol.js"}
          </div>
        </section>
      </div>
    </div>
  );
}
