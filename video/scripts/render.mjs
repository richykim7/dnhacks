import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
const file = process.argv[2];
let output = "out/product-walkthrough-preview.mp4";
const extra = [];
if (file) {
  const props = JSON.parse(readFileSync(file, "utf8"));
  const r = props.reveal;
  if (
    !r?.verified ||
    ![
      "paperTitle",
      "doi",
      "publicationDate",
      "candidate",
      "runId",
      "manifestHash",
      "evidenceNote",
    ].every((k) => typeof r[k] === "string" && r[k].trim())
  )
    throw new Error(
      "Final render needs the verified matching paper, candidate, exact run, manifest, and access-boundary note.",
    );
  output = "out/product-walkthrough.mp4";
  extra.push("--props", path.resolve(file));
} else
  console.log(
    "Rendering a clearly labeled preview: held-out reveal has not been supplied.",
  );
const r = spawnSync(
  process.execPath,
  [
    "node_modules/@remotion/cli/remotion-cli.js",
    "render",
    "ProductWalkthrough",
    output,
    "--codec=h264",
    "--muted",
    "--crf=18",
    "--concurrency=4",
    ...extra,
  ],
  { stdio: "inherit" },
);
process.exit(r.status ?? 1);
