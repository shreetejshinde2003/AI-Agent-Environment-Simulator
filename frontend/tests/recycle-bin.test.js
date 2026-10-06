import {test} from "node:test";
import assert from "node:assert/strict";
import {canManageRecycleBin, canPurgeRecycleBin} from "../src/utils/recycleBin.js";
import {mergeActiveRuns} from "../src/utils/runs.js";

test("recycle bin controls follow personal ownership and organization IAM", () => {
  for (const [workspace, manage, purge] of [
    [null, false, false], [{kind: "personal"}, true, true],
    [{kind: "organization", membershipRole: "owner"}, true, true],
    [{kind: "organization", membershipRole: "admin"}, true, false],
    [{kind: "organization", membershipRole: "member", humanRoles: ["hr_approver"]}, false, false],
  ]) {
    assert.equal(canManageRecycleBin(workspace), manage);
    assert.equal(canPurgeRecycleBin(workspace), purge);
  }
});
test("authoritative refresh removes deleted runs while keeping later evidence for present runs", () => {
  const deleted = {id: "deleted", events: [1, 2]};
  const present = {id: "present", status: "completed", events: [1, 2, 3]};
  assert.deepEqual(mergeActiveRuns([{...present, status: "queued", events: []}], [deleted, present]), [present]);
  assert.deepEqual(mergeActiveRuns([], [deleted]), []);
});
test("acknowledgement during an older refresh survives once but next complete list is authoritative", () => {
  const created = {id: "new", events: [1]};
  assert.deepEqual(mergeActiveRuns([], [created], [created.id]), [created]);
  assert.deepEqual(mergeActiveRuns([], [created], []), []);
});
