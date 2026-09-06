import { useEffect, useState } from "react";
import type { JsonRecord } from "@/lib/types";
import Workbench from "./InhibitorWorkbench";

export default function InhibitorLink() {
  const q = new URLSearchParams(location.search),
    run = decodeURIComponent(location.hash.split("/")[1] || "");
  const experiment = q.get("experiment") || "",
    key = q.get("artifact") || "";
  const params = new URLSearchParams();
  if (q.get("project")) params.set("project", q.get("project")!);
  if (q.has("through")) params.set("through", q.get("through")!);
  const root = `/api/runtime/${encodeURIComponent(run)}`;
  const [artifact, setArtifact] = useState<JsonRecord | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    fetch(`${root}/snapshot?${params}`)
      .then(async (r) => {
        const s = await r.json();
        if (!r.ok) throw Error(s.error);
        const exp = s.runs?.[run]?.experiments?.[experiment];
        const a = exp?.artifacts?.find(
          (a: JsonRecord) =>
            a.storage_key === key &&
            a.kind === "molecular_structure" &&
            a.status === "available",
        );
        if (!a)
          throw Error("Structure absent from owning experiment at this cursor");
        setArtifact(a);
      })
      .catch((e) => setError(e.message));
  }, [run, experiment, key]);
  function close() {
    const u = new URL(location.href);
    for (const name of [
      "experiment",
      "artifact",
      "sceneTool",
      "sceneRevision",
      "sceneActor",
    ])
      u.searchParams.delete(name);
    location.href = u.toString();
  }
  return artifact ? (
    <Workbench
      artifact={artifact}
      experimentId={experiment}
      owner={`${experiment} · ${run}`}
      url={`${root}/geometry/${key}?${params}`}
      onClose={close}
    />
  ) : (
    <div role="alert">
      {error || "Opening owning experiment…"}
      <button onClick={close}>Return to investigation</button>
    </div>
  );
}
