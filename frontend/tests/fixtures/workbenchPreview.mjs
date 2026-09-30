// Optional local smoke harness. Not imported by application/unit test discovery.
// Example: node frontend/tests/fixtures/workbenchPreview.mjs /private/tmp/phase.json
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {readFileSync} from "node:fs";
import {inspectorRuns, fixtureAgents} from "./inspectorRuns.js";
import {liveRunSnapshots, shortAdaptiveRun} from "./liveRunSnapshots.js";

const phasePath = process.argv[2];
const withoutStrict = process.argv.includes("--without-strict");
let blockedWrites = 0;
const fixture = {
  name: "read-only-workbench-fixture",
  enforce: "pre",
  transform(code, id) {
    // Diagnostic only: compare React Flow's StrictMode warning without changing
    // the production entry point or suppressing warnings in the application.
    if (withoutStrict && id.endsWith("/src/main.jsx")) {
      const diagnostic = code.replace("<StrictMode>", "<>").replace("</StrictMode>", "</>");
      console.log("Fixture diagnostic: StrictMode wrapper removed:", diagnostic !== code);
      return diagnostic;
    }
  },
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (!["GET", "HEAD"].includes(req.method)) {
        blockedWrites++; res.statusCode = 405; res.end("Fixture rejects writes"); return;
      }
      const path = req.url.split("?")[0];
      let phase = 0;
      if (phasePath) phase = JSON.parse(readFileSync(phasePath, "utf8")).phase;
      const data = path === "/health" ? {status: "ok"} :
        path === "/api/v1/tasks" ? [shortAdaptiveRun, liveRunSnapshots[phase] ?? liveRunSnapshots[0], ...inspectorRuns] :
        path === "/api/v1/agents" ? fixtureAgents :
        path === "/api/v1/simulations/metrics" ? {summary: {}, agents: [], history: []} :
        path === "/api/v1/datasets" ? [] :
        path === "/fixture-check" ? {blockedWrites, providerForwarding: false, phase, withoutStrict} : undefined;
      if (data !== undefined) {res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(data)); return;}
      if (path.startsWith("/api/") || path.startsWith("/ws/")) {res.statusCode = 404; res.end("No fixture route"); return;}
      next();
    });
  },
};
const server = await createServer({root: fileURLToPath(new URL("../../", import.meta.url)), envDir: false,
  plugins: [fixture], define: {
    "import.meta.env.VITE_API_BASE_URL": JSON.stringify("http://127.0.0.1:5183"),
    "import.meta.env.VITE_WS_URL": JSON.stringify("ws://127.0.0.1:5183/ws/live"),
  }, server: {host: "127.0.0.1", port: 5183, strictPort: true, hmr: false}});
await server.listen();
console.log("Read-only fixture ready on http://127.0.0.1:5183");
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, async () => {await server.close(); process.exit(0);});
