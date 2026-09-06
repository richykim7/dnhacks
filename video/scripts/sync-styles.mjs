// Preserve the application's native CSS; Tailwind build directives belong to Vite.
import { readFile, writeFile } from "node:fs/promises";
const source = await readFile(
  new URL("../../frontend/src/styles.css", import.meta.url),
  "utf8",
);
const start = source.indexOf(":root {");
if (start < 0) throw new Error("Frontend stylesheet has no root token block");
await writeFile(
  new URL("../src/frontend.generated.css", import.meta.url),
  "/* Generated from frontend/src/styles.css by scripts/sync-styles.mjs. */\n" +
    source.slice(start),
);
