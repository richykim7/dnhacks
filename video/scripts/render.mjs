import { spawnSync } from "node:child_process";
import path from "node:path";
const output =
  process.env.VIDEO_OUTPUT || path.resolve("out/latent-nature-walkthrough.mp4");
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
  ],
  { stdio: "inherit" },
);
process.exit(r.status ?? 1);
