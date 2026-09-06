import { useCurrentFrame } from "remotion";
import {
  Frame,
  Shell,
  Heading,
  Button,
  BookOpen,
  ArrowUpRight,
  Cursor,
  tween,
  Status,
} from "../ui";
import corpus from "../corpus.json";
export function Library() {
  const f = useCurrentFrame(),
    n = Math.floor(tween(f, 60, 390, 0, 100));
  return (
    <Frame
      chapter="03 / BUILD THE LIBRARY"
      caption={
        f < 130
          ? "Collect the papers. Keep their sources."
          : f < 350
            ? "Full texts arrive, one paper at a time."
            : "The literature is now a reusable research collection."
      }
      detail="100-paper curated corpus · Ingestion timing is animated"
    >
      <Shell>
        <Heading
          title="Pancreatic cancer"
          sub="Cell survival, division machinery, metabolism, and the tumor environment."
          action={
            <Button variant="default">
              {f < 60 ? "Build collection" : "Ask a research question"}{" "}
              <ArrowUpRight size={18} />
            </Button>
          }
        />
        <div className="library-metrics">
          <div>
            <small>Papers collected</small>
            <strong>
              {n}
              <em>/ 100</em>
            </strong>
          </div>
          <div>
            <small>Collection</small>
            <strong className="word-stat">Full-text literature</strong>
          </div>
          <div>
            <small>Build status</small>
            <Status
              label={n === 100 ? "Ready" : "Fetching full text"}
              tone={n === 100 ? "positive" : "neutral"}
            />
          </div>
        </div>
        <div className="build-progress">
          <span style={{ width: `${n}%` }} />
        </div>
        <div className="library-layout">
          <aside>
            <b>Collections</b>
            <div className="collection-selected">
              <BookOpen size={19} /> Pancreatic cancer
            </div>
            <p>Collection settings</p>
            <p>Documents</p>
            <p>Research assistant</p>
            <p>Builds & runs</p>
          </aside>
          <div className="papers-table">
            <div className="table-label">
              <span>Paper / source</span>
              <span>Year</span>
              <span>Full text</span>
            </div>
            {corpus.papers.slice(0, 7).map((p, i) => (
              <div
                className="paper-row"
                key={p.doi}
                style={{
                  opacity: tween(f, 75 + i * 32, 95 + i * 32),
                  translate: `0 ${tween(f, 75 + i * 32, 104 + i * 32, 24, 0)}px`,
                }}
              >
                <BookOpen size={20} />
                <div>
                  <b>{p.title}</b>
                  <small>{p.doi}</small>
                </div>
                <span>{p.year}</span>
                <span className="paper-check">✓</span>
              </div>
            ))}
          </div>
        </div>
        <Cursor
          points={[
            [0, 947, 498],
            [34, 1310, 82],
            [55, 1310, 82],
            [90, 1100, 540],
            [350, 1100, 540],
            [435, 1290, -35],
            [509, 1290, -35],
          ]}
          clicks={[44, 457]}
        />
      </Shell>
    </Frame>
  );
}
