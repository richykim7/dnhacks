import { AnimatePresence, LayoutGroup, motion } from "motion/react";
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
    title: "Binder interaction",
    short: "Binder interaction",
    scale: "Molecular",
    action: "Open binder node",
    x: 50,
    y: 43,
    question: "Inspect how a binder approaches a target surface.",
    context:
      "The cyan target and coral binder are illustrative molecular shapes. The sequence makes the approach and contact region visible.",
    legend: ["Target surface", "Binder"],
    steps: [
      "Inspect the separate molecular surfaces.",
      "Move the binder toward the target face.",
      "Highlight the contact region between partners.",
      "Hold the arrangement for inspection.",
    ],
    limit:
      "This geometry does not establish binding affinity, selectivity or biological activity.",
  },
  {
    id: "tissue",
    file: "TissueDemo",
    number: "02",
    title: "Tumor–stroma interaction",
    short: "Tumor–stroma interaction",
    scale: "Cellular",
    action: "Open tissue node",
    x: 27,
    y: 72,
    question: "Inspect the arrangement of tumor cells and surrounding stroma.",
    context:
      "Translucent cell membranes show the local neighborhood. Coral stromal cells remain distinct from the cyan tumor compartment.",
    legend: ["Tumor cells", "Stromal cells"],
    steps: [
      "Inspect the cell neighborhood.",
      "Move closer to the local arrangement.",
      "Highlight the central group of cells.",
      "Hold the neighborhood for inspection.",
    ],
    limit:
      "The scene is a composed illustration, not a simulation or measured tissue response.",
  },
  {
    id: "spindle",
    file: "SpindleDemo",
    number: "03",
    title: "Spindle assembly",
    short: "Spindle assembly",
    scale: "Subcellular",
    action: "Open spindle node",
    x: 73,
    y: 72,
    question: "Inspect filament organization around chromosomes.",
    context:
      "Cyan filaments connect two poles inside a translucent cell boundary. Coral chromosomes mark the central interacting structures.",
    legend: ["Filaments and poles", "Chromosomes"],
    steps: [
      "Inspect the poles and initial filaments.",
      "Bring the filament arrangement into alignment.",
      "Highlight the central chromosome region.",
      "Hold the structure for inspection.",
    ],
    limit:
      "The animation does not measure forces, predict division outcomes or report a simulated experiment.",
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
  const [settled, setSettled] = useState(false);
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
    // Warm the primary local scene while the investigation map is visible.
    void modules["./scenes/binder/BinderDemo.tsx"]?.().catch(() => undefined);
  }, []);
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
    setSettled(false);
    setSelected(id);
    setTime(0);
    setPlaying(!reducedMotion);
    setOpened(true);
    setNotice("");
  }
  function close() {
    setSettled(false);
    setOpened(false);
    setPlaying(false);
  }
  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await root.current?.requestFullscreen();
    } catch {
      setNotice("Fullscreen is unavailable in this browser.");
    }
  }
  const phaseIndex = time < 5 ? 0 : time < 11 ? 1 : time < 15 ? 2 : 3;
  const phase = reducedMotion
    ? "Static view"
    : ["Establish", "Approach", "Interaction", "Hold"][phaseIndex];
  const transition = {
    duration: reducedMotion ? 0 : 0.65,
    ease: [0.22, 0.8, 0.2, 1] as const,
  };
  return (
    <LayoutGroup id="cinematic-investigation">
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
            <span className="cine-brand-divider" />
            <span className="cine-workspace">Investigations</span>
          </a>
          <span className="cine-provenance">
            <Sparkles size={12} /> Illustrative demo
          </span>
        </header>
        <div className="cine-workspace-area">
          <motion.main
            className="cine-map-layout"
            inert={opened}
            aria-hidden={opened}
            animate={{ opacity: opened ? 0 : 1 }}
            transition={{ duration: reducedMotion ? 0 : 0.3 }}
          >
            <div className="cine-intro">
              <span className="cine-eyebrow">INVESTIGATION DEMO</span>
              <h1>Biological interactions</h1>
              <p>
                Select a research node to inspect its illustrative experiment.
              </p>
            </div>
            <div className="cine-map" aria-label="Research nodes">
              <svg
                className="cine-connections"
                viewBox="0 0 1000 660"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path d="M500 85 L500 284 M500 284 C500 390 270 370 270 475 M500 284 C500 390 730 370 730 475" />
              </svg>
              <div className="cine-root-node">
                <span />
                Research question
                <small>Biological interactions across scales</small>
              </div>
              {stories.map((s) => (
                <button
                  key={s.id}
                  ref={(el) => {
                    nodeButtons.current[s.id] = el;
                  }}
                  className="cine-node"
                  style={{ left: `${s.x}%`, top: `${s.y}%` }}
                  onClick={() => open(s.id)}
                  onPointerEnter={() => {
                    void modules[`./scenes/${s.id}/${s.file}.tsx`]?.();
                  }}
                  onFocus={() => {
                    void modules[`./scenes/${s.id}/${s.file}.tsx`]?.();
                  }}
                  disabled={!scenes[s.id]}
                  aria-label={s.action}
                >
                  {(!opened || selected !== s.id) && (
                    <motion.span
                      className="cine-node-surface"
                      layoutId={`research-node-${s.id}`}
                      transition={transition}
                      style={{ borderRadius: 12 }}
                    />
                  )}
                  <span className="cine-node-symbol">
                    <span />
                  </span>
                  <span className="cine-node-copy">
                    <small>
                      EXPERIMENT {s.number} · {s.scale}
                    </small>
                    <motion.strong
                      layoutId={`node-title-${s.id}`}
                      transition={transition}
                    >
                      {s.title}
                    </motion.strong>
                    <span>
                      {scenes[s.id]
                        ? "Inspect experiment"
                        : "Scene unavailable"}
                      <ArrowUpRight size={12} />
                    </span>
                  </span>
                </button>
              ))}
            </div>
            <p className="cine-map-provenance">
              Local illustrative geometry. No live investigation or experimental
              results.
            </p>
          </motion.main>
          <AnimatePresence
            initial={false}
            onExitComplete={() => nodeButtons.current[selected]?.focus()}
          >
            {opened && (
              <motion.article
                className={`cine-expanded ${settled ? "is-settled" : ""}`}
                onLayoutAnimationComplete={() => setSettled(true)}
                key={selected}
                layoutId={`research-node-${selected}`}
                transition={transition}
                initial={{
                  backgroundColor: "#0b1b25",
                  borderColor: "#67e8f938",
                }}
                animate={{
                  backgroundColor: "#061019",
                  borderColor: "#67e8f900",
                }}
                style={{
                  borderRadius: 0,
                  borderWidth: 1,
                  borderStyle: "solid",
                }}
                aria-label={`${story.title} expanded node`}
              >
                <div className="cine-expanded-content">
                  <div className="cine-expanded-top">
                    <button
                      className="cine-back"
                      ref={closeButton}
                      onClick={close}
                    >
                      <ArrowLeft size={15} /> Collapse node
                    </button>
                    <span className="cine-node-path">
                      Research question <ChevronRight size={12} /> Experiment{" "}
                      {story.number}
                    </span>
                  </div>
                  <div className="cine-expanded-grid">
                    <div className="cine-render-column">
                      <section className="cine-stage" aria-label={story.title}>
                        <SceneBoundary key={selected}>
                          <Suspense
                            fallback={
                              <div className="cine-message">
                                Loading geometry…
                              </div>
                            }
                          >
                            {Scene ? (
                              <Scene
                                time={time}
                                reducedMotion={reducedMotion}
                              />
                            ) : (
                              <div className="cine-message">
                                Scene unavailable
                              </div>
                            )}
                          </Suspense>
                        </SceneBoundary>
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
                            {playing ? <Pause size={15} /> : <Play size={15} />}
                          </button>
                          <button
                            className="cine-icon-button"
                            onClick={() => {
                              setTime(0);
                              setPlaying(false);
                            }}
                            aria-label="Reset"
                          >
                            <RotateCcw size={15} />
                          </button>
                          <output
                            className="cine-time"
                            aria-label="Elapsed time"
                          >
                            {time.toFixed(1).padStart(4, "0")}
                            <span> / 18.0 s</span>
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
                            aria-label={
                              fullscreen ? "Exit fullscreen" : "Fullscreen"
                            }
                          >
                            {fullscreen ? (
                              <Minimize size={15} />
                            ) : (
                              <Maximize size={15} />
                            )}
                          </button>
                        </div>
                        <div className="cine-transport-caption">
                          <span>{phase}</span>
                          <span role="status">
                            {notice ||
                              (reducedMotion
                                ? "Reduced motion"
                                : "18-second illustrative sequence")}
                          </span>
                        </div>
                      </div>
                    </div>
                    <aside
                      className="cine-info"
                      aria-label="Experiment context"
                    >
                      <span className="cine-eyebrow">
                        EXPERIMENT {story.number} / {story.scale.toUpperCase()}
                      </span>
                      <motion.h1
                        layoutId={`node-title-${selected}`}
                        transition={transition}
                      >
                        {story.title}
                      </motion.h1>
                      <p className="cine-question">{story.question}</p>
                      <div className="cine-context">
                        <h2>Context</h2>
                        <p>{story.context}</p>
                        <div className="cine-legend">
                          {story.legend.map((label, i) => (
                            <span key={label}>
                              <i
                                style={{
                                  background: i ? "#fb8c82" : "#67e8f9",
                                }}
                              />
                              {label}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div className="cine-steps">
                        <h2>Sequence</h2>
                        {story.steps.map((step, i) => (
                          <button
                            key={step}
                            aria-label={`Step ${i + 1}: ${["Establish", "Approach", "Interaction", "Hold"][i]}`}
                            aria-current={
                              !reducedMotion && phaseIndex === i
                                ? "step"
                                : undefined
                            }
                            onClick={() => {
                              setTime([0, 5, 11, 15][i]);
                              setPlaying(false);
                            }}
                          >
                            <span className="cine-step-number">0{i + 1}</span>
                            <span>
                              <strong>
                                {
                                  [
                                    "Establish",
                                    "Approach",
                                    "Interaction",
                                    "Hold",
                                  ][i]
                                }
                              </strong>
                              <small>{step}</small>
                            </span>
                            <span className="cine-step-time">
                              {["0–5s", "5–11s", "11–15s", "15–18s"][i]}
                            </span>
                          </button>
                        ))}
                      </div>
                      <p className="cine-limit">
                        <span>Illustrative only</span>
                        {story.limit}
                      </p>
                    </aside>
                  </div>
                </div>
              </motion.article>
            )}
          </AnimatePresence>
        </div>
      </div>
    </LayoutGroup>
  );
}
