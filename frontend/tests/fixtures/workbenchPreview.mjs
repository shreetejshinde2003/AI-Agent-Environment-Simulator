// Optional local smoke harness. Not imported by application/unit test discovery.
// Example: node frontend/tests/fixtures/workbenchPreview.mjs /private/tmp/phase.json
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {readFileSync} from "node:fs";
import {inspectorRuns, fixtureAgents, singleRun} from "./inspectorRuns.js";
import {liveRunSnapshots, shortAdaptiveRun} from "./liveRunSnapshots.js";
import {acknowledgedFixture, completedFixture, registeredDatasets} from "./composerFixtures.js";

const phasePath = process.argv[2];
const withoutStrict = process.argv.includes("--without-strict");
// Opt-in in-memory acknowledgements for composer QA. Default stays read-only.
// No database, API forwarding, provider or disk writes exist in either mode.
const composerFixture = process.argv.includes("--composer-fixture");
let blockedWrites = 0;
let mockSubmissions = 0, mockUploads = 0, staleReads = 0, createdRun = null;
const config = () => phasePath ? JSON.parse(readFileSync(phasePath, "utf8")) : {};
const reply = (res, data, status = 200) => {res.statusCode = status; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(data));};
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
      const path = req.url.split("?")[0];
      const settings = config();
      if (composerFixture && req.method === "POST" && ["/api/v1/tasks", "/api/v1/uploads"].includes(path)) {
        let body = "";
        req.on("data", chunk => {body += chunk;});
        req.on("end", () => {
          if (path === "/api/v1/uploads") {
            mockUploads++;
            return reply(res, {id: `fixture-upload-${mockUploads}`, filename: new URL(req.url, "http://127.0.0.1").searchParams.get("filename"),
              format: "txt", sizeBytes: Buffer.byteLength(body), preview: body, preparedContext: body,
              truncated: false, columns: [], rowCount: null}, 201);
          }
          mockSubmissions++;
          let payload;
          try {payload = JSON.parse(body);} catch {return reply(res, {detail: "Invalid fixture request"}, 422);}
          setTimeout(() => {
            if (settings.create === "validation") return reply(res, {detail: {code: "invalid_route", message: "Fixture validation rejected this configuration."}}, 422);
            if (settings.create === "unknown") return reply(res, {detail: "Fixture service outcome unavailable"}, 503);
            createdRun = acknowledgedFixture(payload, mockSubmissions);
            staleReads = settings.staleReads ?? 2;
            reply(res, createdRun, 201);
          }, settings.createDelayMs ?? 1200);
        });
        return;
      }
      if (!["GET", "HEAD"].includes(req.method)) {
        blockedWrites++; res.statusCode = 405; res.end("Fixture rejects writes"); return;
      }
      const phase = settings.phase ?? 0;
      const tasks = settings.runs === "empty" ? [] : [shortAdaptiveRun, liveRunSnapshots[phase] ?? liveRunSnapshots[0], ...inspectorRuns];
      if (settings.largeHistory) tasks.push(...Array.from({length: 80}, (_, index) => ({...singleRun,
        id: `fixture-archive-${index}`, title: `Fixture archive ${index} ${"long accessible run title ".repeat(4)}`,
        createdAt: `2026-09-01T10:${String(index % 60).padStart(2, "0")}:00Z`})));
      if (createdRun && path === "/api/v1/tasks") {
        if (staleReads > 0) staleReads--;
        else tasks.unshift(settings.createdPhase === "completed" ? completedFixture(createdRun) : createdRun);
      }
      if (path === "/api/v1/datasets" && settings.datasets === "error") return reply(res, {detail: "Fixture registry unavailable"}, 503);
      const data = path === "/health" ? {status: "ok"} :
        path === "/api/v1/tasks" ? tasks :
        path === "/api/v1/agents" ? fixtureAgents :
        path === "/api/v1/simulations/metrics" ? {summary: {}, agents: [], history: []} :
        path === "/api/v1/datasets" ? settings.datasets === "registered" ? registeredDatasets : [] :
        path === "/fixture-check" ? {blockedWrites, providerForwarding: false, phase, withoutStrict, composerFixture, mockSubmissions, mockUploads, staleReads} : undefined;
      if (data !== undefined) {reply(res, data); return;}
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
console.log(`${composerFixture ? "In-memory composer" : "Read-only"} fixture ready on http://127.0.0.1:5183`);
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, async () => {await server.close(); process.exit(0);});
