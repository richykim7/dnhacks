import { lazy, Suspense, useState } from "react";
import { Loading } from "./common";
import { runtimeUrl, type RuntimeEvent } from "@/lib/runtime";
import type { JsonRecord } from "@/lib/types";

const BinderWorkbench = lazy(() => import("./binder/Workbench"));
const Structures = lazy(() => import("./Structures"));
const InhibitorWorkbench = lazy(() => import("./InhibitorWorkbench"));

export type SceneChoice = { key: string; experiment: JsonRecord; artifact: JsonRecord };

/** One exact collected artifact, kept mounted while its research activity changes. */
export default function NodeScene({ choices, active, onSelect, onClose, events, runId, project, cursor }: {
  choices: SceneChoice[]; active: SceneChoice; onSelect: (key: string) => void; onClose: () => void;
  events: RuntimeEvent[]; runId: string; project: string; cursor: number | null;
}) {
  const { artifact, experiment } = active;
  const [inhibitorKey, setInhibitorKey] = useState<string | null>(null);
  const url = runtimeUrl(runId, `blob/${artifact.storage_key}`, project, cursor);
  return <section className="node-scene" aria-label="Research scene">
    <header className="node-scene-header">
      <label>Scene source
        <select aria-label="Scene source" value={active.key} onChange={e => onSelect(e.target.value)}>
          {choices.map(c => <option key={c.key} value={c.key} data-bundle-sha256={c.artifact.sha256} data-source-experiment={c.experiment.experiment_id}>
            {c.experiment.title || "Experiment"} · {c.artifact.name || c.artifact.kind}
          </option>)}
        </select>
      </label>
      <button className="node-scene-close" onClick={onClose} aria-label="Close scene workspace">×</button>
      {inhibitorKey === active.key && <button onClick={() => setInhibitorKey(null)}>Return to reference</button>}
      <span>{artifact.provenance?.category?.replaceAll("_", " ") || "Recorded source"}</span>
    </header>
    <div className="node-scene-object" data-scene-experiment-id={experiment.experiment_id}>
      <Suspense fallback={<Loading label="Opening research scene" />}>
        {artifact.kind === "binder_bundle" ? <BinderWorkbench
          key={active.key} sha256={artifact.sha256} url={url}
          candidates={choices.filter(c => c.experiment.experiment_id === experiment.experiment_id && c.artifact.kind === "binder_bundle")
            .map(c => ({ sha256: c.artifact.sha256, name: c.artifact.name,
              url: runtimeUrl(runId, `blob/${c.artifact.storage_key}`, project, cursor) }))
            .filter((c, index, all) => all.findIndex(other => other.sha256 === c.sha256) === index)}
          sceneActions={events.filter(e => e.kind === "scene.recipe" &&
            e.experiment_id === experiment.experiment_id && e.payload.bundle_sha256 === artifact.sha256)
            .map(e => ({ sequence: e.sequence, note: e.payload.note,
              recipe_sha256: e.payload.recipe.sha256, view: e.payload.view }))}
        /> : inhibitorKey === active.key ? <InhibitorWorkbench key={artifact.sha256} embedded
          experimentId={experiment.experiment_id} owner={`${experiment.title || "Experiment"} · ${runId}`}
          artifact={artifact} url={url.replace('/blob/', '/geometry/')} onClose={() => setInhibitorKey(null)} />
          : <Structures key={active.key} experimentId={experiment.experiment_id}
          onOpenWorkbench={() => setInhibitorKey(active.key)}
          owner={`${experiment.title || "Experiment"} · ${runId}`} artifact={artifact} url={url} />}
      </Suspense>
    </div>
  </section>;
}
