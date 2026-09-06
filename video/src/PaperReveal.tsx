import { AbsoluteFill, Img, interpolate, staticFile, Easing } from "remotion";
export const discovery = {
  title:
    "Stress adaptation pathways and HA–CD44 signaling maintain the survival of pancreatic cancer cells with centrosome amplification",
  doi: "10.1186/s12964-026-02865-5",
  date: "7 April 2026",
  candidate:
    "HA–CD44 supports division tolerance in centrosome-amplified pancreatic cells",
  run: "pdac-frozen-investigation-03~1~1~1~1~1~1~1~1~1",
  candidateId: 900004,
};
const ramp = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });
export function PaperReveal({ frame }: { frame: number }) {
  return (
    <AbsoluteFill className="paper-scene">
      <div className="paper-heading">THE HELD-OUT PAPER</div>
      <div className="paper-story">
        <h1>
          The connection
          <br />
          in the paper.
        </h1>
        <p>
          HA production.
          <br />
          CD44 signaling.
          <br />
          Tolerance of extra centrosomes.
        </p>
        <div className="candidate-reveal-label">HA–CD44 candidate / 900004</div>
        <div className="paper-citation">
          Ozcan et al. · Cell Communication and Signaling
          <br />
          {discovery.date}
          <br />
          doi:{discovery.doi}
        </div>
      </div>
      <div
        className="actual-paper"
        style={{
          opacity: ramp(frame, 25, 60),
          translate: "0 " + 40 * (1 - ramp(frame, 25, 70)) + "px",
        }}
      >
        <Img src={staticFile("capture/held-out-paper.png")} />
      </div>
      <div className="paper-credit">
        Actual article first page · © The Author(s) 2026 · CC BY-NC-ND 4.0
      </div>
    </AbsoluteFill>
  );
}
export function EvidenceBoundary({ frame }: { frame: number }) {
  return (
    <AbsoluteFill
      className="paper-scene boundary-scene"
      style={{ opacity: ramp(frame, 0, 15) }}
    >
      <div className="paper-heading">AFTER THE REVEAL / WHAT WAS HELD OUT</div>
      <h1>
        Earlier literature.
        <br />
        An excluded comparison paper.
      </h1>
      <div className="evidence-columns">
        <section>
          <span>01</span>
          <h2>The collection</h2>
          <p>
            100 full-text papers.
            <br />
            Publication years 2007–2025.
            <br />
            Curation boundary: 25 Jan 2026.
          </p>
        </section>
        <section>
          <span>02</span>
          <h2>The paper</h2>
          <p>
            Published 7 April 2026.
            <br />
            Its DOI is absent from the frozen corpus and its paper index.
          </p>
        </section>
        <section>
          <span>03</span>
          <h2>The comparison</h2>
          <p>
            The HA–CD44 candidate connects metabolic adaptation with division
            tolerance in pancreatic cell models.
          </p>
        </section>
      </div>
      <p className="evidence-provenance">
        Presentation reconstruction from the repository’s demo history; not an
        independently measured holdout recovery.
        <br />A frozen corpus alone does not rule out pretrained model
        knowledge.
      </p>
      <div className="latent-end">
        Latent Nature
        <span>Follow the evidence. Explore the next question.</span>
      </div>
    </AbsoluteFill>
  );
}
