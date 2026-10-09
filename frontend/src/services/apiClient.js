import {creationError} from "../utils/apiErrors";
import { API_BASE_URL } from "./apiConfig";
import { parseApiResponse, requireResponseType } from "./apiResponse";
import { sessionHeaders } from "./sessionSync";
export { API_BASE_URL, WS_URL } from "./apiConfig";
function workspaceHeaders(workspaceId) {
  return workspaceId ? {"X-Workspace-Id": workspaceId} : {};
}
async function request(path, options = {}) {
  const response = await fetch(API_BASE_URL + "/api/v1" + path, {
    ...options,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...sessionHeaders(), ...options.headers },
    signal: options.signal ?? AbortSignal.timeout(15000),
  });
  return parseApiResponse(response, "/api/v1" + path);
}
export const apiClient = {
  getResearchBenchmarks: (workspaceId, signal) => request("/experiments/benchmarks", {headers:workspaceHeaders(workspaceId), signal}),
  getResearchExperiments: (workspaceId, signal) => request("/experiments/research", {headers:workspaceHeaders(workspaceId), signal}),
  getResearchExperiment: (id, workspaceId, signal) => request("/experiments/research/"+encodeURIComponent(id), {headers:workspaceHeaders(workspaceId), signal}),
  getResearchRun: (id, workspaceId, signal) => request("/tasks/"+encodeURIComponent(id), {headers:workspaceHeaders(workspaceId), signal}),
  createResearchExperiment: (payload, workspaceId) => request("/experiments/research", {method:"POST",body:JSON.stringify(payload),headers:workspaceHeaders(workspaceId)}).catch(error=>{throw creationError(error);}),
  rerunResearchExperiment: (id, workspaceId) => request("/experiments/research/"+encodeURIComponent(id)+"/rerun", {method:"POST",headers:workspaceHeaders(workspaceId)}).catch(error=>{throw creationError(error);}),
  reviewResearchRun: (id, taskId, payload, workspaceId) => request("/experiments/research/"+encodeURIComponent(id)+"/runs/"+encodeURIComponent(taskId)+"/human-review",{method:"POST",body:JSON.stringify(payload),headers:workspaceHeaders(workspaceId)}),
  exportResearchExperiment: (id, workspaceId, signal) => request("/experiments/research/"+encodeURIComponent(id)+"/report",{headers:workspaceHeaders(workspaceId),signal}),
  getHRReviewCapabilities: (workspaceId, signal) => request("/hiring/reviews/capabilities", {headers: workspaceHeaders(workspaceId), signal}),
  getHRReviews: (workspaceId, signal) => request("/hiring/reviews", {headers: workspaceHeaders(workspaceId), signal}),
  getHRReview: (id, workspaceId) => request("/hiring/reviews/" + encodeURIComponent(id), {headers: workspaceHeaders(workspaceId)}),
  getHRReviewHistory: (id, workspaceId) => request("/hiring/reviews/" + encodeURIComponent(id) + "/history", {headers: workspaceHeaders(workspaceId)}),
  submitHRReview: (payload, workspaceId) => request("/hiring/reviews", {method:"POST", body:JSON.stringify(payload), headers:workspaceHeaders(workspaceId)}),
  decideHRReview: (id, payload, approval, workspaceId) => request("/hiring/reviews/" + encodeURIComponent(id) + (approval ? "/approval" : "/review"),
    {method:"POST", body:JSON.stringify(payload), headers:workspaceHeaders(workspaceId)}),
  getHRAgents: (workspaceId, signal) => request("/hiring/agents", {headers: workspaceHeaders(workspaceId), signal}),
  getHRRuns: (workspaceId, signal) => request("/hiring/agents/runs", {headers: workspaceHeaders(workspaceId), signal}),
  getHRRun: (id, workspaceId) => request("/hiring/agents/runs/" + encodeURIComponent(id), {headers: workspaceHeaders(workspaceId)}),
  runHRAgent: (payload, workspaceId) => request("/hiring/agents/runs", {method: "POST", body: JSON.stringify(payload), headers: workspaceHeaders(workspaceId)}),
  getHiringCapabilities: (workspaceId, signal) => request("/hiring/capabilities", {headers: workspaceHeaders(workspaceId), signal}),
  getHiringRecords: (kind, workspaceId, signal) => request("/hiring/" + kind, {headers: workspaceHeaders(workspaceId), signal}),
  getHiringRevisions: (kind, id, workspaceId) => request("/hiring/" + kind + "/" + encodeURIComponent(id) + "/revisions", {headers: workspaceHeaders(workspaceId)}),
  getLinkedJobDescriptions: (kind, id, revision, workspaceId, signal) => request("/hiring/" + kind + "/" + encodeURIComponent(id) + "/revisions/" + revision + "/job-descriptions", {headers:workspaceHeaders(workspaceId), signal}),
  saveHiringRecord: (kind, id, payload, workspaceId) => request("/hiring/" + kind + (id ? "/" + encodeURIComponent(id) : ""),
    {method: id ? "PUT" : "POST", body: JSON.stringify(payload), headers: workspaceHeaders(workspaceId)}),
  getAgents: workspaceId => request("/agents", {headers: workspaceHeaders(workspaceId)}),
  getCustomAgents: workspaceId => request("/agent-builder", {headers: workspaceHeaders(workspaceId)}),
  getAgentBuilderOptions: workspaceId => request("/agent-builder/options", {headers: workspaceHeaders(workspaceId)}),
  getCustomAgentRevisions: (id, workspaceId) => request("/agent-builder/" + encodeURIComponent(id) + "/revisions", {headers: workspaceHeaders(workspaceId)}),
  saveCustomAgent: (id, payload, workspaceId) => request("/agent-builder" + (id ? "/" + encodeURIComponent(id) : ""),
    {method: id ? "PUT" : "POST", body: JSON.stringify(payload), headers: workspaceHeaders(workspaceId)}),
  runCustomAgent: (id, payload, workspaceId) => request("/agent-builder/" + encodeURIComponent(id) + "/runs",
    {method: "POST", body: JSON.stringify(payload), headers: workspaceHeaders(workspaceId)}).catch(error => {throw creationError(error);}),
  getAgentRelationships: () => request("/agents/relationships"),
  createAgent: payload => request("/agents", {method: "POST", body: JSON.stringify(payload)}),
  getTasks: workspaceId => request("/tasks", {headers: workspaceHeaders(workspaceId)}),
  getTask: (id, workspaceId) => request("/tasks/" + encodeURIComponent(id), {headers: workspaceHeaders(workspaceId)}),
  getRecycleBin: workspaceId => request("/recycle-bin", {headers: workspaceHeaders(workspaceId)}),
  deleteRun: (id, workspaceId) => request("/simulations/" + encodeURIComponent(id),
    {method: "DELETE", headers: workspaceHeaders(workspaceId)}),
  restoreRun: (id, workspaceId) => request("/recycle-bin/simulations/" + encodeURIComponent(id) + "/restore",
    {method: "POST", headers: workspaceHeaders(workspaceId)}),
  purgeRun: (id, workspaceId) => request("/recycle-bin/simulations/" + encodeURIComponent(id),
    {method: "DELETE", body: JSON.stringify({confirmPermanentDeletion: true}), headers: workspaceHeaders(workspaceId)}),
  getDatasets: () => request("/datasets"),
  createTask: (payload, workspaceId) => request("/tasks", {method: "POST", body: JSON.stringify(payload), headers: workspaceHeaders(workspaceId)}).catch(error => {throw creationError(error);}),
  getMetrics: workspaceId => request("/simulations/metrics", {headers: workspaceHeaders(workspaceId)}),
  getMessages: (limit = 50, workspaceId) => request("/messages?limit=" + limit, {headers: workspaceHeaders(workspaceId)}),
  getSimulationStats: workspaceId => request("/simulation/stats", {headers: workspaceHeaders(workspaceId)}),
  getActivityFeed: (limit = 20, workspaceId) => request("/simulation/activity?limit=" + limit, {headers: workspaceHeaders(workspaceId)}),
  upload: (file, workspaceId) => request("/uploads?filename=" + encodeURIComponent(file.name),
    {method: "POST", body: file, headers: {...workspaceHeaders(workspaceId),
      "Content-Type": file.type || "application/octet-stream"}}),
  async exportRun(id, format, workspaceId) {
    const response = await fetch(API_BASE_URL + "/api/v1/simulations/" + encodeURIComponent(id) +
      "/export?format=" + format, {credentials: "include", headers: {...sessionHeaders(), ...workspaceHeaders(workspaceId)}, signal: AbortSignal.timeout(15000)});
    const requestPath = "/api/v1/simulations/" + encodeURIComponent(id) + "/export";
    if (!response.ok) await parseApiResponse(response, requestPath);
    requireResponseType(response, requestPath, {json: "application/json", txt: "text/plain", csv: "text/csv"}[format]);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url; link.download = id + "." + format;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
