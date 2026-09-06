import { useCurrentFrame } from "remotion";
import { Frame, Shell, Cursor, tween, C, Button } from "../ui";
const labels = [
  "Pancreatic cancer",
  "Cell division",
  "Nutrient stress",
  "Microtubules",
  "Tumor environment",
  "Cell survival",
  "ATF4",
  "Metabolism",
  "KRAS",
  "Redox balance",
  "DNA damage",
  "Stroma",
  "ERK signaling",
  "Autophagy",
  "Protein stress",
  "Mitotic spindle",
  "Glutamine",
  "Fibroblasts",
  "Checkpoint",
  "Immune cells",
  "Matrix signaling",
  "Apoptosis",
  "Mitochondria",
  "Growth factors",
];
export const kgNodes = Array.from({ length: 66 }, (_, i) => {
  const angle = i * 2.39996;
  const r = i === 0 ? 0 : 72 + Math.sqrt(i) * 37;
  return {
    x: 660 + Math.cos(angle) * r * 1.42,
    y: 325 + Math.sin(angle) * r * 0.77,
    label: labels[i % labels.length],
    start: 30 + i * 4.3,
  };
});
export function Knowledge() {
  const f = useCurrentFrame();
  return (
    <Frame
      chapter="04 / CONNECT THE EVIDENCE"
      caption={
        f < 180
          ? "Each paper contributes claims, entities, and source evidence."
          : f < 370
            ? "Connections accumulate into a knowledge graph."
            : "A map of what is known—and where to investigate next."
      }
      detail="Illustrative graph growth · Entity labels drawn from the corpus scope"
    >
      <Shell tab="Knowledge">
        <div className="graph-top">
          <div>
            <h1>Knowledge</h1>
            <p>Pancreatic cancer / Literature graph</p>
          </div>
          <Button variant="default">Start an investigation ↗</Button>
          <div className="graph-legend">
            <i /> Literature claim <span>○</span> Entity
          </div>
        </div>
        <svg className="kg-stage" viewBox="0 0 1456 620">
          <defs>
            <pattern
              id="grid"
              width="26"
              height="26"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r=".65" fill="#485b53" opacity=".45" />
            </pattern>
          </defs>
          <rect width="1456" height="620" fill="url(#grid)" />
          <g
            style={{
              transformOrigin: "660px 325px",
              scale: tween(f, 100, 460, 1.33, 0.93),
            }}
          >
            {kgNodes.slice(1).map((p, i) => {
              const q = kgNodes[Math.floor(i / 2)];
              return (
                <line
                  key={i}
                  x1={q.x}
                  y1={q.y}
                  x2={p.x}
                  y2={p.y}
                  stroke={i % 7 === 0 ? C.accent : "#526960"}
                  strokeWidth="1.4"
                  pathLength="1"
                  strokeDasharray="1"
                  strokeDashoffset={1 - tween(f, p.start - 5, p.start + 22)}
                  opacity={0.7}
                />
              );
            })}
            {kgNodes.map((p, i) => (
              <g key={i} opacity={tween(f, p.start, p.start + 19)}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={i === 0 ? 14 : i < 24 ? 8 : 4}
                  fill={i % 3 === 0 ? C.accent : "#65877b"}
                  stroke="#dceae2"
                  strokeWidth={i < 24 ? 1 : 0}
                />
                {i < 24 && (
                  <text x={p.x + 13} y={p.y + 5} fontSize="15" fill={C.fg}>
                    {p.label}
                  </text>
                )}
              </g>
            ))}
          </g>
        </svg>
        <div className="graph-source" style={{ opacity: tween(f, 240, 270) }}>
          <small>SOURCE-GROUNDED CLAIM</small>
          <b>Nutrient shortage → cellular stress response</b>
          <p>Open the supporting paper and its quoted evidence.</p>
        </div>
        <Cursor
          points={[
            [0, 1088, 39],
            [80, 938, 332],
            [230, 938, 332],
            [295, 1020, 559],
            [490, 753, 51],
            [539, 753, 51],
          ]}
          clicks={[240, 515]}
        />
      </Shell>
    </Frame>
  );
}
