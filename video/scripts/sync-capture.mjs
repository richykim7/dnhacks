import { readFile, writeFile } from "node:fs/promises";
const file = new URL("../public/capture/manifest.json", import.meta.url);
const raw = await readFile(file, "utf8").catch(() => {
  throw new Error(
    "Capture the current app first: npm run capture. See README for capture output configuration.",
  );
});
const d = JSON.parse(raw);
if (!d.captures.length || d.captures.at(-1).t < 140)
  throw new Error("The app capture is incomplete. Resume it before rendering.");
await writeFile(new URL("../src/capture.generated.json", import.meta.url), raw);
