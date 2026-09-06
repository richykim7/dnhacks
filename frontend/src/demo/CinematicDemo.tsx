import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  ChevronRight,
  Maximize,
  Minimize,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { DEMO_DURATION, type DemoSceneId, type DemoSceneProps } from "./types";
import "./cinematic.css";

const modules = import.meta.glob<{ default: ComponentType<DemoSceneProps> }>(
  "./scenes/*/*Demo.tsx",
);
const stories = [
  {
    id: "binder",
    file: "BinderDemo",
    number: "01",
    title: "A meeting at the interface",
    short: "Binder interface",
    question: "How might two molecular surfaces meet?",
    description:
      "Follow a designed partner toward a complementary surface. Shape, approach and contact become a spatial story.",
    scale: "Molecular",
    action: "Explore the interface",
    x: 50,
    y: 42,
  },
  {
    id: "tissue",
    file: "TissueDemo",
    number: "02",
    title: "A neighborhood in exchange",
    short: "Living tissue",
    question: "How do cells shape their surroundings?",
    description:
      "Move from individual cells to a layered neighborhood, where local exchange connects the scene.",
    scale: "Cellular",
    action: "Enter the neighborhood",
    x: 27,
    y: 69,
  },
  {
    id: "spindle",
    file: "SpindleDemo",
    number: "03",
    title: "An architecture of motion",
    short: "Spindle assembly",
    question: "How does a shared structure emerge?",
    description:
      "Trace a luminous filament architecture as interacting elements approach and reorganize.",
    scale: "Subcellular",
    action: "Follow the filaments",
    x: 75,
    y: 67,
  },
] as const;
const scenes = Object.fromEntries(
  stories.map((s) => {
    const loader = modules[`./scenes/${s.id}/${s.file}.tsx`];
    return [s.id, loader ? lazy(loader) : null];
  }),
) as Record<DemoSceneId, ComponentType<DemoSceneProps> | null>;

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
      <div className="cine-message">
        This scene could not open. Return to the map and try again.
      </div>
    ) : (
      this.props.children
    );
  }
}
function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}
export default function CinematicDemo() {
  const [selected, setSelected] = useState<DemoSceneId>("binder");
  const [opened, setOpened] = useState(false);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [notice, setNotice] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const nodeButtons = useRef<
    Partial<Record<DemoSceneId, HTMLButtonElement | null>>
  >({});
  const reducedMotion = useReducedMotion();
  const story = stories.find((s) => s.id === selected)!;
  const Scene = scenes[selected];
  useEffect(() => {
    if (!playing || !opened) return;
    let frame: number;
    let previous: number | undefined;
    const tick = (now: number) => {
      // Capture the delta before React may defer the state updater.
      const delta = previous === undefined ? 0 : (now - previous) / 1000;
      previous = now;
      if (delta) setTime((t) => Math.min(DEMO_DURATION, t + delta));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, opened]);
  useEffect(() => {
    if (time >= DEMO_DURATION) setPlaying(false);
  }, [time]);
  useEffect(() => {
    if (reducedMotion) setPlaying(false);
  }, [reducedMotion]);
  useEffect(() => {
    const changed = () =>
      setFullscreen(document.fullscreenElement === root.current);
    const visibility = () => {
      if (document.hidden) setPlaying(false);
    };
    document.addEventListener("fullscreenchange", changed);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      document.removeEventListener("fullscreenchange", changed);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  useEffect(() => {
    if (opened) closeButton.current?.focus();
  }, [opened]);
  function open(id: DemoSceneId) {
    setSelected(id);
    setTime(0);
    setPlaying(!reducedMotion);
    setOpened(true);
    setNotice("");
  }
  function close() {
    setOpened(false);
    setPlaying(false);
    requestAnimationFrame(() => nodeButtons.current[selected]?.focus());
  }
  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await root.current?.requestFullscreen();
    } catch {
      setNotice("Fullscreen is unavailable in this browser.");
    }
  }
  const phase = reducedMotion
    ? "Static view"
    : time < 5
      ? "Establish"
      : time < 11
        ? "Approach"
        : time < 15
          ? "Interaction"
          : "Hold";
  return (
    <div
      className={`cinematic-demo ${opened ? "is-open" : ""}`}
      ref={root}
      onKeyDown={(e) => {
        if (e.key === "Escape" && opened && !fullscreen) close();
      }}
    >
      <header className="cine-header">
        <a
          className="cine-brand"
          href="/"
          aria-label="Return to research workspace"
        >
          <span className="cine-mark">d</span> discovery
          <span className="cine-brand-divider" />{" "}
          <span className="cine-workspace">Research workspace</span>
        </a>
        <span className="cine-provenance">
          <Sparkles size={13} /> Illustrative demo
        </span>
      </header>
      {!opened ? (
        <main className="cine-map-layout">
          <div className="cine-intro">
            <span className="cine-eyebrow">
              INVESTIGATIONS / VISUAL STORIES
            </span>
            <h1>
              Follow the question.
              <br />
              <span>See the possibility.</span>
            </h1>
            <p>
              Explore three scales of biological interaction.
              <br />
              Select a node to step inside the idea.
            </p>
          </div>
          <div className="cine-map" aria-label="Curated investigation map">
            <svg
              className="cine-connections"
              viewBox="0 0 1000 660"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="cine-edge" x1="0" y1="0" x2="0" y2="1">
                  <stop stopColor="#67e8f9" stopOpacity=".55" />
                  <stop offset="1" stopColor="#67e8f9" stopOpacity=".12" />
                </linearGradient>
              </defs>
              <path d="M500 90 C500 175 500 190 500 277 M500 277 C500 355 270 330 270 455 M500 277 C500 350 750 330 750 442" />
              <path
                className="cine-edge-muted"
                d="M270 455 C270 510 155 495 155 565 M270 455 C270 510 380 500 380 570 M750 442 C750 505 640 500 640 565 M750 442 C750 510 865 485 865 558"
              />
              <g className="cine-leaves">
                <circle cx="155" cy="565" r="4" />
                <circle cx="380" cy="570" r="4" />
                <circle cx="640" cy="565" r="4" />
                <circle cx="865" cy="558" r="4" />
              </g>
            </svg>
            <div className="cine-root-node">
              <span /> Biology, in relation
              <small>A curated investigation</small>
            </div>
            {stories.map((s) => (
              <button
                key={s.id}
                ref={(el) => {
                  nodeButtons.current[s.id] = el;
                }}
                className={`cine-node ${s.id === "binder" ? "cine-node-principal" : ""}`}
                style={{ left: `${s.x}%`, top: `${s.y}%` }}
                onClick={() => open(s.id)}
                disabled={!scenes[s.id]}
                aria-label={`${s.action}${!scenes[s.id] ? " — coming soon" : ""}`}
              >
                <span className="cine-node-orbit">
                  <span className="cine-node-core" />
                </span>
                <span className="cine-node-label">
                  <small>
                    {s.number} / {s.scale}
                  </small>
                  <strong>{s.short}</strong>
                  <span>
                    {scenes[s.id] ? (
                      <>
                        Open visual story <ArrowUpRight size={12} />
                      </>
                    ) : (
                      "Scene arriving soon"
                    )}
                  </span>
                </span>
              </button>
            ))}
            <span className="cine-map-caption">
              ONE QUESTION · THREE PERSPECTIVES
            </span>
          </div>
          <aside className="cine-map-note">
            <span className="cine-note-line" />
            <p>
              From molecular contact
              <br />
              to collective behavior.
            </p>
            <small>
              Curated geometry and animation.
              <br />
              No experimental results are shown.
            </small>
          </aside>
          <footer className="cine-map-footer">
            <span>LOCAL VISUAL COLLECTION</span>
            <span>Shape. Context. Interaction.</span>
            <span>01 — 03</span>
          </footer>
        </main>
      ) : (
        <main className="cine-theater">
          <div className="cine-theater-top">
            <button ref={closeButton} className="cine-back" onClick={close}>
              <ArrowLeft size={15} /> Investigation map
            </button>
            <div className="cine-scene-tabs" aria-label="Scene selection">
              {stories.map((s) => (
                <button
                  key={s.id}
                  disabled={!scenes[s.id]}
                  aria-label={s.short}
                  aria-pressed={selected === s.id}
                  onClick={() => open(s.id)}
                >
                  {s.number}
                  <span>{s.short}</span>
                </button>
              ))}
            </div>
          </div>
          <section className="cine-stage" aria-label={story.short}>
            <SceneBoundary key={selected}>
              <Suspense
                fallback={
                  <div className="cine-message">Opening visual story…</div>
                }
              >
                {Scene ? (
                  <Scene time={time} reducedMotion={reducedMotion} />
                ) : (
                  <div className="cine-message">
                    This visual story is being prepared.
                  </div>
                )}
              </Suspense>
            </SceneBoundary>
            <div className="cine-stage-heading">
              <span className="cine-eyebrow">
                {story.number} / {story.scale.toUpperCase()} PERSPECTIVE
              </span>
              <h1>{story.title}</h1>
              <p>{story.question}</p>
            </div>
            <div className="cine-stage-corner">
              <span className="cine-cyan-dot" />
              {phase}
              <small>ILLUSTRATIVE GEOMETRY</small>
            </div>
          </section>
          <div className="cine-transport">
            <div className="cine-transport-row">
              <button
                className="cine-play"
                onClick={() => {
                  if (time >= DEMO_DURATION) setTime(0);
                  setPlaying((p) => !p);
                }}
                aria-label={playing ? "Pause" : "Play"}
              >
                {playing ? <Pause size={17} /> : <Play size={17} />}
              </button>
              <button
                className="cine-icon-button"
                onClick={() => {
                  setTime(0);
                  setPlaying(false);
                }}
                aria-label="Reset"
              >
                <RotateCcw size={17} />
              </button>
              <output className="cine-time" aria-label="Elapsed time">
                {time.toFixed(1).padStart(4, "0")} <span>/ 18.0 s</span>
              </output>
              <input
                className="cine-scrubber"
                type="range"
                min="0"
                max="18"
                step="0.01"
                value={time}
                aria-label="Scene time"
                aria-valuetext={`${time.toFixed(1)} seconds, ${phase}`}
                onChange={(e) => {
                  setTime(Number(e.target.value));
                  setPlaying(false);
                }}
                style={
                  {
                    "--progress": `${(time / DEMO_DURATION) * 100}%`,
                  } as React.CSSProperties
                }
              />
              <button
                className="cine-icon-button"
                onClick={toggleFullscreen}
                aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
              >
                {fullscreen ? <Minimize size={17} /> : <Maximize size={17} />}
              </button>
            </div>
            <div className="cine-chapters">
              {["Establish", "Approach", "Interaction", "Hold"].map((p, i) => (
                <button
                  key={p}
                  aria-current={p === phase ? "step" : undefined}
                  onClick={() => {
                    setTime([0, 5, 11, 15][i]);
                    setPlaying(false);
                  }}
                >
                  <span>0{i + 1}</span>
                  {p}
                  <ChevronRight size={11} />
                </button>
              ))}
            </div>
          </div>
          <footer className="cine-scene-footer">
            <p>{story.description}</p>
            <span role="status">
              {notice ||
                (reducedMotion
                  ? "Reduced motion · static composition"
                  : "Curated animation · no experimental measurements")}
            </span>
          </footer>
        </main>
      )}
    </div>
  );
}
