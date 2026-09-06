import { Frame, Shell, Button, Status, Cursor, Field, Typed } from "../ui";
import { useCurrentFrame } from "remotion";
import { RevealData, renderReady } from "../story";
export function Review({ reveal }: { reveal: RevealData }) {
  const f = useCurrentFrame();
  return (
    <Frame
      chapter="07 / INSPECT THE CANDIDATE"
      caption={
        f < 150
          ? "Open a candidate and inspect the evidence behind it."
          : "Verification and human review are separate steps."
      }
      detail={
        renderReady(reveal)
          ? `Investigation ${reveal.runId}`
          : "Illustrative review workflow · No scientific result is asserted"
      }
    >
      <Shell tab="Investigations">
        <div className="review-layout">
          <aside>
            <small>INVESTIGATION / CANDIDATES</small>
            <h2>Candidate review</h2>
            <div className="candidate-item">
              <Status label="Needs review" />
              <h3>{reveal.candidate || "A connection worth testing"}</h3>
              <p>Inspect experiment, evidence, and limitations.</p>
            </div>
          </aside>
          <main>
            <small>RESEARCH RECORD</small>
            <h1>
              {reveal.candidate ||
                "From a promising connection to a reviewable claim"}
            </h1>
            <div className="review-grid">
              <div>
                <h3>01 / Evidence</h3>
                <p>Read the supporting claims and source papers.</p>
              </div>
              <div>
                <h3>02 / Experiment</h3>
                <p>Inspect the analysis code, result, and controls.</p>
              </div>
              <div>
                <h3>03 / Verification</h3>
                <p>Review the gate verdict and its stated limitations.</p>
              </div>
            </div>
            <Field label="Human review note" tall>
              <Typed
                text="Check the mechanism, evidence, and limitations before deciding whether to accept the candidate."
                start={135}
                speed={1.5}
              />
            </Field>
            <div className="review-actions">
              <Button>Request more evidence</Button>
              <Button variant="default">Record review</Button>
            </div>
          </main>
        </div>
        <Cursor
          points={[
            [0, 1255, 675],
            [38, 264, 302],
            [95, 264, 302],
            [147, 687, 460],
            [295, 1130, 610],
            [359, 1130, 610],
          ]}
          clicks={[50, 150]}
        />
      </Shell>
    </Frame>
  );
}
