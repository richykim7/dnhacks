import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { request } from "@/lib/api";
import { DEMO_DURATION, type DemoSceneId } from "@/demo/types";
import { Button } from "./ui/button";
import { ErrorNotice, Loading } from "./common";

const scenes = {
  binder: lazy(() => import("@/demo/scenes/binder/BinderDemo")),
  tissue: lazy(() => import("@/demo/scenes/tissue/TissueDemo")),
  spindle: lazy(() => import("@/demo/scenes/spindle/SpindleDemo")),
};
interface Illustration {
  schema: "illustrative_scene.v1";
  scene: DemoSceneId;
  title: string;
  purpose: string;
  provenance: { category: "illustrative"; description: string };
}
function parseIllustration(value: unknown): Illustration {
  const data = value as Partial<Illustration> | null;
  if (
    !data ||
    data.schema !== "illustrative_scene.v1" ||
    !["binder", "tissue", "spindle"].includes(data.scene ?? "") ||
    typeof data.title !== "string" ||
    !data.title.trim() ||
    typeof data.purpose !== "string" ||
    !data.purpose.trim() ||
    data.provenance?.category !== "illustrative" ||
    typeof data.provenance.description !== "string" ||
    !data.provenance.description.trim()
  )
    throw new Error("Recorded scene descriptor is invalid.");
  return data as Illustration;
}
class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <ErrorNotice message="This simulation could not render. Close the scene and try again." />
    ) : (
      this.props.children
    );
  }
}

/** A recorded illustration selects local geometry; it never supplies executable content. */
export default function IllustrativeScene({ url }: { url: string }) {
  const identity = new URL(url, window.location.origin);
  identity.searchParams.delete("through");
  const source = identity.toString();
  const [record, setRecord] = useState<{
    source: string;
    data: Illustration;
  }>();
  const [error, setError] = useState("");
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [cameraReset, setCameraReset] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => {
      setReducedMotion(query.matches);
      if (query.matches) setPlaying(false);
    };
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    setError("");
    void request<unknown>(url, { signal: abort.signal })
      .then(parseIllustration)
      .then((data) => {
        if (!abort.signal.aborted) {
          setRecord({ source, data });
        }
      })
      .catch((e: Error) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [url, source]);
  const data = record?.source === source ? record.data : undefined;
  const loadedSource = data ? source : undefined;
  useEffect(() => {
    setTime(0);
    setPlaying(
      Boolean(loadedSource) &&
        !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
  }, [loadedSource]);
  useEffect(() => {
    if (!playing || reducedMotion) return;
    let frame = 0;
    let previous: number | undefined;
    const tick = (now: number) => {
      const delta =
        previous === undefined ? 0 : Math.min(0.1, (now - previous) / 1000);
      previous = now;
      if (!document.hidden) setTime((t) => Math.min(DEMO_DURATION, t + delta));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, reducedMotion]);
  useEffect(() => {
    if (time >= DEMO_DURATION) setPlaying(false);
  }, [time]);

  // RuntimeDetail removes unavailable artifacts on rewind. An immutable descriptor
  // can retain its local animation time while the investigation cursor advances.
  if (error) return <ErrorNotice message={error} />;
  if (!data) return <Loading label="Opening simulation" />;
  const Scene = scenes[data.scene];
  return (
    <section aria-label="Simulation" data-illustrative-scene={data.scene}>
      <p>
        <strong>Simulation</strong>
      </p>
      <h3>{data.title}</h3>
      <p>{data.purpose}</p>
      <SceneBoundary key={source}>
        <div
          style={{
            height: "clamp(340px, 54vh, 680px)",
            width: "100%",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          <Suspense fallback={<Loading label="Opening animation" />}>
            <Scene
              key={`${source}:${cameraReset}`}
              time={time}
              reducedMotion={reducedMotion}
              interactive
            />
          </Suspense>
        </div>
      </SceneBoundary>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginTop: 12,
          flexWrap: "wrap",
        }}
      >
        <Button
          size="sm"
          variant="ghost"
          disabled={reducedMotion}
          onClick={() => {
            if (time >= DEMO_DURATION) setTime(0);
            setPlaying((value) => !value);
          }}
        >
          {playing ? <Pause size={14} /> : <Play size={14} />}
          {playing ? "Pause simulation" : "Play simulation"}
        </Button>
        <Button
          size="icon"
          variant="ghost"
          aria-label="Reset simulation time"
          onClick={() => {
            setTime(0);
            setPlaying(false);
          }}
        >
          <RotateCcw size={14} />
        </Button>
        <input
          aria-label="Simulation time"
          type="range"
          min={0}
          max={DEMO_DURATION}
          step={0.1}
          value={time}
          disabled={reducedMotion}
          style={{ minWidth: 40, flex: 1 }}
          onChange={(event) => {
            setPlaying(false);
            setTime(Number(event.target.value));
          }}
        />
        <small>{time.toFixed(1)} s</small>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setCameraReset((value) => value + 1)}
        >
          Reset camera
        </Button>
      </div>
      <small className="muted">
        Drag to rotate · Scroll to zoom · Right-drag to pan
      </small>
    </section>
  );
}
