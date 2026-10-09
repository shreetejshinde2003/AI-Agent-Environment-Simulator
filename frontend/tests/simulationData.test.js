import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {resolveAcknowledgedRuns} from '../src/utils/acknowledgedRuns.js';
import {mergeRuns, mergeActiveRuns} from '../src/utils/runs.js';

// Exercise the real hook with controlled hook slots and deferred API reads.
// No timer, browser, server, or added test dependency is needed for this race.
const source = (await readFile(new URL('../src/hooks/useSimulationData.js', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '').replace('export function useSimulationData', 'function useSimulationData');
const tick = () => new Promise(resolve => setImmediate(resolve));
function world() {
  const slots = [], effects = [], requests = [];
  let cursor = 0, workspaceId = 'A', workspaceStatus = 'ready', hook;
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const api = name => id => new Promise((resolve, reject) => requests.push({name, id, resolve, reject}));
  const context = {
    useState(initial) {
      const n = cursor++;
      if (!(n in slots)) slots[n] = typeof initial === 'function' ? initial() : initial;
      return [slots[n], next => {slots[n] = typeof next === 'function' ? next(slots[n]) : next;}];
    },
    useRef(initial) {const n = cursor++; return slots[n] ??= {current: initial};},
    useCallback(fn, deps) {
      const n = cursor++;
      if (!same(slots[n]?.deps, deps)) slots[n] = {fn, deps};
      return slots[n].fn;
    },
    useEffect(fn, deps) {
      const n = cursor++;
      if (!same(slots[n]?.deps, deps)) effects.push(() => {
        slots[n]?.cleanup?.(); slots[n] = {deps, cleanup: fn()};
      });
    },
    apiClient: {getAgents: api('agents'), getTasks: api('tasks'), getMetrics: api('metrics'), getTask: (taskId, id) => new Promise((resolve, reject) => requests.push({name: 'detail', taskId, id, resolve, reject}))},
    useWorkspace: () => ({activeWorkspaceId: workspaceId, status: workspaceStatus}),
    useBackendConnection: () => 'connected', useLiveSocket: () => 'connected',
    mergeRuns, mergeActiveRuns, resolveAcknowledgedRuns, setInterval: () => 1, clearInterval() {},
  };
  hook = vm.runInNewContext(source + '\nuseSimulationData;', context);
  const render = (id = workspaceId, commit = true) => {
    workspaceId = id; cursor = 0; const result = hook();
    if (commit) {while (effects.length) effects.shift()();}
    return result;
  };
  const resolve = (id, title) => requests.filter(r => r.id === id && !r.done).forEach(r => {
    r.done = true; r.resolve(r.name === 'tasks' ? Array.isArray(title) ? title : [{id: title, workspaceId: id}] : r.name === 'agents' ? [] : {summary: {}});
  });
  return {render, resolve, requests, setWorkspaceStatus: value => {workspaceStatus = value;}};
}

test('workspace change immediately hides prior simulation evidence before effects run', async () => {
  const h = world(); h.render(); h.resolve('A', 'private-A'); await tick();
  assert.equal(h.render().tasks[0].id, 'private-A');
  const switched = h.render('B', false);
  assert.equal(switched.tasks.length, 0);
  assert.equal(switched.hasLoaded, false);
  assert.equal(switched.lastRefreshedAt, null);
});

test('A to B to A rejects the original delayed response and loads a fresh snapshot', async () => {
  const h = world(); h.render(); h.render('B'); h.render('A');
  h.resolve('A', 'obsolete-response'); await tick();
  assert.equal(h.render().tasks.length, 0);
  h.resolve('A', 'fresh-response'); await tick();
  assert.equal(h.render().tasks[0].id, 'fresh-response');
});

test('A to B to A discards an old error after the original request fails', async () => {
  const h = world(); h.render(); h.render('B'); h.render('A');
  h.requests.find(r => r.name === 'tasks').reject(new Error('obsolete-error'));
  await tick();
  assert.equal(h.render().error, null);
  h.resolve('A', 'current-response'); await tick();
  assert.equal(h.render().tasks[0].id, 'current-response');
});

test('late creation acknowledgement cannot inject a run into another workspace', async () => {
  const h = world(); h.render(); h.resolve('A', 'existing-A'); await tick();
  const old = h.render(); h.render('B');
  old.acceptRun({id: 'late-A', workspaceId: 'A'});
  assert.equal(h.render().tasks.length, 0);
  const current = h.render();
  current.acceptRun({id: 'new-B', workspaceId: 'B'});
  assert.equal(h.render().tasks[0].id, 'new-B');
});


test('health success alone does not enable creation before authenticated data loads', () => {
  const h = world();
  assert.equal(h.render().connectionStatus, 'connecting');
  const noWorkspace = h.render(null);
  assert.equal(noWorkspace.connectionStatus, 'connecting');
  assert.equal(noWorkspace.backendStatus, 'connected');
});

test('workspace bootstrap failure cannot display operational REST or endless loading', () => {
  const h = world(); h.setWorkspaceStatus('error');
  const state = h.render(null);
  assert.equal(state.connectionStatus, 'disconnected');
  assert.equal(state.workspaceStatus, 'error');
  assert.equal(state.isLoading, false);
});


test('acknowledged run survives stale lists only while detail evidence confirms it', async () => {
  const h = world(); h.render(); h.resolve('A', []); await tick();
  const run = {id: 'created-A', workspaceId: 'A', status: 'queued'};
  h.render().acceptRun(run);
  h.render().refresh(); h.resolve('A', []); await tick();
  const detail = h.requests.find(r => r.name === 'detail');
  assert.equal(detail.taskId, run.id); assert.equal(detail.id, 'A');
  detail.done = true; detail.resolve(run); await tick();
  assert.equal(h.render().tasks[0].id, run.id);
  h.render().refresh(); h.resolve('A', [run]); await tick();
  h.render().refresh(); h.resolve('A', []); await tick();
  assert.equal(h.render().tasks.length, 0);
  assert.equal(h.requests.filter(r => r.name === 'detail').length, 1);
});

test('delayed acknowledged detail cannot leak evidence after workspace switch', async () => {
  const h = world(); h.render(); h.resolve('A', []); await tick();
  const run = {id: 'created-A', workspaceId: 'A', status: 'queued'};
  h.render().acceptRun(run);
  h.render().refresh(); h.resolve('A', []); await tick();
  const detail = h.requests.find(r => r.name === 'detail');
  h.render('B'); detail.done = true; detail.resolve(run); await tick();
  h.resolve('B', []); await tick();
  assert.equal(h.render().tasks.length, 0);
  assert.equal(h.render().hasLoaded, true);
});


test('refresh feedback is pending during a read and clears on success or failure', async () => {
  const h = world(); h.render();
  assert.equal(h.render().isRefreshing, true);
  h.resolve('A', []); await tick();
  assert.equal(h.render().isRefreshing, false);
  h.render().refresh();
  assert.equal(h.render().isRefreshing, true);
  h.requests.filter(r => r.name === 'tasks' && !r.done).forEach(r => {r.done = true; r.reject(new Error('fixture retry failure'));});
  await tick();
  assert.equal(h.render().isRefreshing, false);
  assert.equal(h.render().error.message, 'fixture retry failure');
});
