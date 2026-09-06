import { createServer } from "vite";
import { writeFileSync, renameSync } from "node:fs";
import { join } from "node:path";
import { createServer as createHttpServer } from "node:http";

const runDir = process.env.E2E_RUN_DIR;
if (!runDir) throw new Error("Use npm run e2e to start an isolated test server.");
const server = await createServer({
  cacheDir: join(runDir, "vite-cache"),
  server: { middlewareMode: true, hmr: false },
});
const httpServer = createHttpServer(server.middlewares);
await new Promise((resolve, reject) => {
  httpServer.once("error", reject);
  httpServer.listen(0, "127.0.0.1", resolve);
});
const { port } = httpServer.address();
const ready = join(runDir, "vite.json");
writeFileSync(`${ready}.tmp`, JSON.stringify({ url: `http://127.0.0.1:${port}` }));
renameSync(`${ready}.tmp`, ready);
