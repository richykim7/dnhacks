import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  Easing,
} from "remotion";
import capture from "./capture.generated.json";
import { PaperReveal, EvidenceBoundary } from "./PaperReveal";
const shots = [...capture.captures].sort((a, b) => a.t - b.t);
const cursor = [...capture.cursor].sort((a, b) => a.t - b.t);
const chapters = [
  [0, "01 / OPEN THE WORKSPACE", "Start with a literature collection."],
  [5, "02 / DEFINE YOUR AREA", "Give your research topic a home."],
  [24, "03 / ADD THE LITERATURE", "Add papers by DOI or upload."],
  [
    35,
    "04 / EXPLORE THE LIBRARY",
    "Full text, figures, and evidence in one place.",
  ],
  [
    52,
    "05 / BUILD THE KNOWLEDGE GRAPH",
    "Published claims become connected evidence.",
  ],
  [
    69,
    "06 / ASK A QUESTION",
    "Which adaptations let cells tolerate extra centrosomes?",
  ],
  [
    86,
    "07 / FOLLOW THE INVESTIGATION",
    "Start with the lead researcher and the evidence.",
  ],
  [
    95,
    "07 / FOLLOW THE INVESTIGATION",
    "Inspect the metabolic branch: one question at a time.",
  ],
  [
    104,
    "08 / EXPAND THE SEARCH",
    "The search accelerates. The research tree unfolds.",
  ],
  [
    126,
    "09 / THE HA–CD44 CONNECTION",
    "HA production and CD44 converge on division tolerance.",
  ],
  [
    134,
    "10 / REVIEW THE CANDIDATE",
    "Open the candidate and inspect its supporting evidence.",
  ],
] as const;
const ease = Easing.bezier(0.22, 1, 0.36, 1);
function Pointer({ seconds }: { seconds: number }) {
  let i = 0;
  while (i + 1 < cursor.length && cursor[i + 1].t <= seconds) i++;
  const a = cursor[i],
    b = cursor[Math.min(i + 1, cursor.length - 1)];
  const progress =
    a === b
      ? 0
      : interpolate(seconds, [Math.max(a.t, b.t - 0.8), b.t], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: ease,
        });
  const x = a.x + (b.x - a.x) * progress,
    y = a.y + (b.y - a.y) * progress;
  const click = cursor.find(
    (p) => p.click && seconds >= p.t && seconds < p.t + 0.45,
  );
  const quiet = seconds >= 104 && seconds < 125;
  return (
    <div
      className="capture-pointer"
      style={{
        left: quiet ? 1840 : x,
        top: quiet ? 940 : y,
        opacity: seconds > 141 ? 0 : 1,
      }}
    >
      {click && (
        <div
          className="capture-click"
          style={{
            scale: 1 + (seconds - click.t) * 4,
            opacity: 1 - (seconds - click.t) / 0.45,
          }}
        />
      )}
      <svg width="28" height="36" viewBox="0 0 33 43">
        <path
          d="M3 2L28 25L17 26L24 38L18 41L11 29L3 36Z"
          fill="#fff"
          stroke="#101914"
          strokeWidth="2"
        />
      </svg>
    </div>
  );
}
export function CapturedWalkthrough() {
  const frame = useCurrentFrame(),
    seconds = frame / 30;
  if (seconds >= 160) return <EvidenceBoundary frame={frame - 4800} />;
  if (seconds >= 146) return <PaperReveal frame={frame - 4380} />;
  let index = 0;
  while (index + 1 < shots.length && shots[index + 1].t <= seconds) index++;
  const shot = shots[index],
    previous = shots[Math.max(index - 1, 0)];
  const animated =
    shot.note.includes("growth") ||
    shot.note.includes("Accelerating") ||
    shot.note.includes("arriving");
  const fade = animated ? Math.min(1, (seconds - shot.t) * 10) : 1;
  const chapter = [...chapters].reverse().find((c) => seconds >= c[0])!;
  return (
    <AbsoluteFill className="capture-video">
      <div className="capture-screen">
        {animated && fade < 1 && (
          <Img
            className="captured-ui"
            src={staticFile("capture/" + previous.file)}
          />
        )}
        <Img
          className="captured-ui"
          src={staticFile("capture/" + shot.file)}
          style={{ opacity: fade }}
        />
        <Pointer seconds={seconds} />
      </div>
      <div className="capture-caption">
        <span>{chapter[1]}</span>
        <b>{chapter[2]}</b>
        <small>{seconds >= 86 ? "Recorded demo history" : ""}</small>
      </div>
    </AbsoluteFill>
  );
}
