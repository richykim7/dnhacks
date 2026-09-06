import { lazy, Suspense } from "react";
import { Loading } from "./common";
import { runtimeUrl, type RuntimeEvent } from "@/lib/runtime";
import type { JsonRecord } from "@/lib/types";

const BinderWorkbench = lazy(() => import("./binder/Workbench"));
const Structures = lazy(() => import("./Structures"));

export type SceneChoice = { key: string; experiment: JsonRecord; artifact: JsonRecord };

/** One exact collected artifact, kept mounted while its research activity changes. */
export default function NodeScene({ choices, active, onSelect, onClose, events, runId, project, cursor }: {
  choices: SceneChoice[]; active: SceneChoice; onSelect: (key: string) => void; onClose: () => void;
  events: RuntimeEvent[]; runId: string; project: string; cursor: number | null;
}) {
  const { artifact, experiment } = active;
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
      <span>{artifact.provenance?.category?.replaceAll("_", " ") || "Recorded source"}</span>
    </header>
    <div className="node-scene-object" data-scene-experiment-id={experiment.experiment_id}>
      <Suspense fallback={<Loading label="Opening research scene" />}>
        {artifact.kind === "binder_bundle" ? <BinderWorkbench
          key={active.key} sha256={artifact.sha256} url={url}
          sceneActions={events.filter(e => e.kind === "scene.recipe" &&
            e.experiment_id === experiment.experiment_id && e.payload.bundle_sha256 === artifact.sha256)
            .map(e => ({ sequence: e.sequence, note: e.payload.note,
              recipe_sha256: e.payload.recipe.sha256, view: e.payload.view }))}
        /> : <Structures key={active.key} experimentId={experiment.experiment_id}
          owner={`${experiment.title || "Experiment"} · ${runId}`} artifact={artifact} url={url} />}
      </Suspense>
    </div>
  </section>;
}
