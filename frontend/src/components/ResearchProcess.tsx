import { useResource } from "@/lib/api";
import type { JsonRecord } from "@/lib/types";
import { Disclosure, ErrorNotice, Loading, Modal } from "./common";
const descriptions: Record<string, { title: string; body: string }> = {
  find: {
    title: "Find relevant literature",
    body: "Search the literature and follow references to build a collection around your topic.",
  },
  extract: {
    title: "Connect claims to their evidence",
    body: "Extract directional claims, preserve supporting quotations, and connect references to their sources.",
  },
  engine: {
    title: "Explore competing explanations",
    body: "Researchers follow different approaches. Selected branches continue; a challenge branch tests alternative explanations.",
  },
  sandbox: {
    title: "Run analyses",
    body: "Experiments execute in isolated containers with resource limits. Their code and outputs are recorded for inspection.",
  },
  falsifier: {
    title: "Check the strength of the result",
    body: "Audited statistics are checked for sample size, direction, the null hypothesis and robustness. Passing these checks is not proof of a discovery.",
  },
  promote: {
    title: "Make the final review",
    body: "A person reviews candidate findings and writes a rationale. Accepted evidence is promoted; rejected findings receive corrective feedback.",
  },
};
export function ResearchProcess({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const architecture = useResource<{ nodes: JsonRecord[] }>(
    open ? "/api/architecture" : null,
  );
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="How the research works"
      description="The engine explores hypotheses and records evidence. You can inspect its work at each stage."
    >
      <ErrorNotice message={architecture.error} />
      {architecture.loading && <Loading />}
      {architecture.data?.nodes
        .filter((n) => descriptions[n.id])
        .map((n) => (
          <section className="process-step" key={n.id}>
            <h3>{descriptions[n.id].title}</h3>
            <p>{descriptions[n.id].body}</p>
            <Disclosure title="Implementation details">
              <ul>
                {n.detail?.map((d: string, i: number) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
              <code>{n.source}</code>
            </Disclosure>
          </section>
        ))}
    </Modal>
  );
}
