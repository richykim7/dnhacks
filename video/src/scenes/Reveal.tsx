import { AbsoluteFill, useCurrentFrame } from "remotion";
import { tween } from "../ui";
import { RevealData, renderReady } from "../story";
export function Reveal({ reveal }: { reveal: RevealData }) {
  const f = useCurrentFrame(),
    ready = renderReady(reveal);
  return (
    <AbsoluteFill className="movie reveal">
      <div className="reveal-kicker">
        {ready ? "THE PAPER REVEAL" : "PAPER REVEAL / AWAITING SOURCE"}
      </div>
      <h1>
        {ready
          ? "A later paper.\nThe same connection."
          : "The final connection."}
      </h1>
      <p className="reveal-sub">
        {ready
          ? "Compare the candidate with the finding in the excluded paper."
          : "This ending is ready for the selected held-out discovery."}
      </p>
      <div
        className="paper-reveal"
        style={{
          opacity: tween(f, 55, 100),
          translate: `0 ${tween(f, 55, 100, 35, 0)}px`,
          rotate: `${tween(f, 55, 110, -2, 0)}deg`,
        }}
      >
        <div className="paper-masthead">
          {ready ? "PUBLISHED RESEARCH" : "SOURCE REQUIRED"}
        </div>
        <h2>
          {reveal.paperTitle ||
            "Attach the matching paper and verified investigation record"}
        </h2>
        <div className="paper-rule" />
        <p>
          {ready
            ? reveal.candidate
            : "The current demo notes do not identify a verified held-out recovery."}
        </p>
        <small>
          {ready
            ? `${reveal.publicationDate} / doi:${reveal.doi}`
            : "No discovery claim is made in this preview."}
        </small>
      </div>
    </AbsoluteFill>
  );
}
export function Boundary({ reveal }: { reveal: RevealData }) {
  return (
    <AbsoluteFill className="movie boundary">
      <div className="reveal-kicker">
        AFTER THE REVEAL / THE EVIDENCE BOUNDARY
      </div>
      <h1>What could the investigator see?</h1>
      <div className="boundary-columns">
        <div>
          <span>01</span>
          <h2>The literature</h2>
          <p>
            100 curated full-text papers.
            <br />
            Publication years 2007–2025.
          </p>
        </div>
        <div>
          <span>02</span>
          <h2>The boundary</h2>
          <p>
            {renderReady(reveal)
              ? reveal.evidenceNote
              : "Curation boundary: 25 January 2026. Run-specific access boundary awaits verification."}
          </p>
        </div>
        <div>
          <span>03</span>
          <h2>The comparison</h2>
          <p>
            {renderReady(reveal)
              ? "The matching paper is evaluated separately from the accessible evidence."
              : "Bind the excluded paper to the exact candidate, run, and corpus manifest."}
          </p>
        </div>
      </div>
      <p className="boundary-note">
        A frozen corpus alone does not rule out pretrained model knowledge.
      </p>
      <div className="boundary-brand">
        DN Research <span>Follow the evidence. Explore the next question.</span>
      </div>
    </AbsoluteFill>
  );
}
