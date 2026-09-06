import { useCurrentFrame } from "remotion";
import { Frame, Shell, Cursor, tween, C, GitBranch, Status } from "../ui";
const topics = [
  "Map the evidence",
  "Test a mechanistic bridge",
  "Division machinery",
  "Nutrient stress",
  "Microenvironment",
  "Check context specificity",
  "Compare alternative explanations",
  "Run a computational experiment",
  "Challenge the result",
  "Inspect negative controls",
  "Trace the supporting literature",
  "Assess candidate mechanism",
];
// First two nodes have long dwell times; descendants accelerate continuously.
export const births = Array.from({ length: 43 }, (_, i) =>
  i === 0 ? 20 : i === 1 ? 165 : 410 + Math.sqrt(i - 1) * 65,
);
export const nodes = births.map((born, i) => {
  const depth = Math.floor(Math.log2(i + 1));
  const first = 2 ** depth - 1;
  const row = i - first;
  return {
    born,
    x: 95 + depth * 342,
    y: 360 + (row - (Math.min(2 ** depth, births.length - first) - 1) / 2) * 52,
    title: topics[i % topics.length],
    depth,
  };
});
function Detail({ second, f }: { second: boolean; f: number }) {
  const base = second ? 180 : 40;
  const lines = second
    ? [
        "Read supporting papers",
        "Form a testable hypothesis",
        "Write analysis code",
        "Compare with a negative control",
      ]
    : [
        "Search the knowledge graph",
        "Read the source evidence",
        "Identify an untested connection",
        "Choose the next research action",
      ];
  return (
    <div className="research-detail">
      <div className="detail-eyebrow">
        RESEARCHER {second ? "02" : "01"} / ACTIVITY
      </div>
      <h2>{second ? "Test a mechanistic bridge" : "Map the evidence"}</h2>
      <p>
        {second
          ? "Does this connection hold beyond general growth inhibition?"
          : "Find connections between cellular stress and division machinery."}
      </p>
      <div className="activity-list">
        {lines.map((line, i) => (
          <div
            key={line}
            style={{ opacity: tween(f, base + i * 28, base + i * 28 + 15) }}
          >
            <span className="activity-bullet" />
            <div>
              <b>{line}</b>
              <small>
                {
                  [
                    "Literature → graph",
                    "Evidence → question",
                    "Question → experiment",
                    "Result → next action",
                  ][i]
                }
              </small>
            </div>
          </div>
        ))}
      </div>
      {second && (
        <pre className="code-preview">{`# Inspect a candidate mechanism
load_evidence()
compare_independent_units()
check_direction_and_controls()
submit_for_review()`}</pre>
      )}
      <div className="detail-footer">
        <Status label="Illustrative research sequence" />
      </div>
    </div>
  );
}
export function Investigation() {
  const f = useCurrentFrame(),
    wide = tween(f, 380, 870),
    second = f >= 165,
    count = births.filter((x) => x <= f).length;
  const caption =
    f < 155
      ? "Researcher 1 reads the evidence and identifies a connection."
      : f < 380
        ? "Researcher 2 turns that connection into a testable question."
        : f < 740
          ? "The investigation branches. More questions run in parallel."
          : "Zoom out: a growing research tree, with evidence behind every step.";
  return (
    <Frame
      chapter="06 / FOLLOW THE RESEARCH"
      caption={caption}
      detail="Authored research sequence · Time compressed; node counts are illustrative"
    >
      <Shell tab="Investigations">
        <div className="investigation-top">
          <div>
            <small>Pancreatic cancer / Investigation</small>
            <h1>Division stress and cellular adaptation</h1>
          </div>
          <div>
            <span className="live-dot" />{" "}
            {f < 410 ? "Researching" : `${count} research nodes`}{" "}
            <span className="speed-badge">
              {f < 410 ? "1×" : `${Math.round(1 + tween(f, 410, 870, 0, 15))}×`}
            </span>
          </div>
        </div>
        <div className="tree-stage">
          <div
            className="tree-world"
            style={{
              scale: 1 - wide * 0.52,
              translate: `${wide * 120}px ${wide * 25}px`,
              transformOrigin: "0 360px",
            }}
          >
            <svg width="2140" height="810" className="tree-edges">
              {nodes.slice(1).map((n, i) => {
                const p = nodes[Math.floor(i / 2)];
                return (
                  <path
                    key={i}
                    d={`M${p.x + 274},${p.y + 61 - wide * 36} C${p.x + 314},${p.y + 61 - wide * 36} ${n.x - 40},${n.y + 61 - wide * 36} ${n.x},${n.y + 61 - wide * 36}`}
                    stroke={i % 8 === 0 ? C.accent : "#658078"}
                    fill="none"
                    strokeWidth="2"
                    pathLength="1"
                    strokeDasharray="1"
                    strokeDashoffset={1 - tween(f, n.born - 8, n.born + 13)}
                  />
                );
              })}
            </svg>
            {nodes.map((n, i) => (
              <div
                className={`movie-agent agent-node ${i === (second ? 1 : 0) && f < 410 ? "selected" : ""} ${wide > 0.3 ? "overview-node" : ""}`}
                key={i}
                style={{
                  left: n.x,
                  top: n.y,
                  opacity: tween(f, n.born, n.born + 14),
                  translate: `0 ${tween(f, n.born, n.born + 20, 13, 0)}px`,
                }}
              >
                <div className="agent-node-top">
                  <span className="agent-kind">
                    <GitBranch size={14} />
                    {i === 0 ? "Lead researcher" : `Research branch ${i}`}
                  </span>
                  <span className="activity-dot live" />
                </div>
                <h3>{n.title}</h3>
                <p>
                  {i === 0
                    ? "Explore the literature"
                    : "Investigate a focused question"}
                </p>
                <div className="agent-node-bottom">
                  <span>{i < 2 ? "Inspect activity" : "Researching"}</span>
                  <span>↗</span>
                </div>
              </div>
            ))}
          </div>
          {f < 460 && (
            <div style={{ opacity: 1 - tween(f, 380, 460) }}>
              <Detail second={second} f={f} />
            </div>
          )}
          <div className="tree-controls">
            − <span>{Math.round((1 - wide * 0.52) * 100)}%</span> +{" "}
            <span>Fit view</span>
          </div>
        </div>
        <Cursor
          points={[
            [0, 1000, 574],
            [45, 244, 391],
            [100, 244, 391],
            [180, 533, 365],
            [310, 1000, 550],
            [415, 1263, 560],
            [700, 1263, 560],
            [1079, 1263, 560],
          ]}
          clicks={[55, 192, 423]}
        />
      </Shell>
    </Frame>
  );
}
