import { useCurrentFrame } from "remotion";
import {
  Frame,
  Shell,
  Heading,
  Button,
  Modal,
  Field,
  Typed,
  Cursor,
  ArrowUpRight,
} from "../ui";
export function Project() {
  const f = useCurrentFrame();
  return (
    <Frame
      chapter="02 / DEFINE THE LITERATURE"
      caption={
        f < 245
          ? "Describe the area you want to explore."
          : "Set the scope before asking the research question."
      }
    >
      <Shell project="All projects">
        <Heading
          title="Your research library"
          sub="A literature collection is the foundation for every investigation."
        />
        <Modal
          title="Create a research project"
          description="Start with a topic. You can refine the literature search and add documents next."
        >
          <Field label="Project name">
            <Typed text="Pancreatic cancer" start={48} speed={3} />
          </Field>
          <Field label="What does this collection cover?" tall>
            <Typed
              text="Pancreatic cancer cell survival under abnormal cell division. Include division machinery, nutrient use, cellular stress, and the tumor environment."
              start={165}
              speed={1.55}
            />
          </Field>
          <div className="modal-actions">
            <Button variant="default">
              Create project <ArrowUpRight size={18} />
            </Button>
          </div>
        </Modal>
        <Cursor
          points={[
            [0, 810, 535],
            [35, 626, 245],
            [100, 626, 245],
            [147, 624, 365],
            [400, 624, 365],
            [452, 947, 498],
            [509, 947, 498],
          ]}
          clicks={[44, 151, 469]}
        />
      </Shell>
    </Frame>
  );
}
