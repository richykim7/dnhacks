import { Frame, Shell, Heading, Button, Empty, Plus, Cursor } from "../ui";
export function Welcome() {
  return (
    <Frame
      chapter="01 / OPEN THE WORKSPACE"
      caption="Every investigation starts with a body of literature."
    >
      <Shell project="All projects">
        <Heading
          title="Your research library"
          sub="A literature collection is the foundation for every investigation."
          action={
            <Button>
              <Plus size={18} /> New project
            </Button>
          }
        />
        <div className="welcome-empty">
          <Empty
            title="Create your first research project"
            action={
              <Button variant="default">
                Create a research project <Plus size={18} />
              </Button>
            }
          >
            Define a topic, collect its literature, and turn the evidence into
            an investigation.
          </Empty>
        </div>
        <Cursor
          points={[
            [0, 1020, 640],
            [90, 1020, 640],
            [140, 728, 452],
            [239, 728, 452],
          ]}
          clicks={[162]}
        />
      </Shell>
    </Frame>
  );
}
