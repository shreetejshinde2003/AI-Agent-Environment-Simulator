import {test} from "node:test";
import assert from "node:assert/strict";
import {resolveAcknowledgedRuns} from "../src/utils/acknowledgedRuns.js";
test("stale list omission resolves acknowledged run from real detail evidence", async () => {
  const created = {id: "created", workspaceId: "WS-fixture", status: "queued"};
  const calls = [];
  const resolved = await resolveAcknowledgedRuns([], [created.id], async id => {calls.push(id);return created;});
  assert.deepEqual(resolved, [created]); assert.deepEqual(calls, [created.id]);
});
test("listed acknowledgement makes no redundant detail request", async () => {
  const tasks = [{id: "created", status: "completed"}];
  assert.deepEqual(await resolveAcknowledgedRuns(tasks, ["created"], () => assert.fail("unexpected detail call")), tasks);
});
test("confirmed deletion or inaccessible run is removed on 404", async () => {
  assert.deepEqual(await resolveAcknowledgedRuns([], ["created"], async () => {throw Object.assign(new Error("not found"), {status: 404});}), []);
});
test("network, permission and server failures cannot masquerade as removal", async () => {
  for (const status of [undefined, 401, 403, 503]) {
    await assert.rejects(resolveAcknowledgedRuns([], ["created"], async () => {throw Object.assign(new Error("fixture unavailable"), {status});}), /fixture unavailable/);
  }
});
test("unacknowledged historical omissions are not resurrected", async () => {
  assert.deepEqual(await resolveAcknowledgedRuns([], [], () => assert.fail("unexpected detail call")), []);
});
