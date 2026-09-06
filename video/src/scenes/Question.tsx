import {
  Frame,
  Shell,
  Heading,
  Modal,
  Field,
  Typed,
  Button,
  ArrowUpRight,
  Cursor,
} from "../ui";
export function Question() {
  return (
    <Frame
      chapter="05 / START AN INVESTIGATION"
      caption="Now ask a question of the collection."
    >
      <Shell tab="Investigations">
        <Heading
          title="Investigations"
          sub="Follow the questions, experiments, and evidence."
        />
        <Modal
          title="Start an investigation"
          description="Ask a question of your literature collection."
        >
          <Field label="Research question" tall>
            <Typed
              text="Which overlooked dependencies allow pancreatic tumor cells to keep dividing despite abnormal division machinery?"
              start={40}
              speed={1.65}
            />
          </Field>
          <div className="research-budget">
            ⌄ Research budget <span>30 actions</span>
          </div>
          <div className="modal-actions">
            <Button variant="default">
              Start research <ArrowUpRight size={18} />
            </Button>
          </div>
        </Modal>
        <Cursor
          points={[
            [0, 1040, 590],
            [30, 618, 280],
            [235, 618, 280],
            [290, 947, 478],
            [359, 947, 478],
          ]}
          clicks={[34, 316]}
        />
      </Shell>
    </Frame>
  );
}
