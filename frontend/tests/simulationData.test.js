import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {mergeRuns, mergeActiveRuns} from '../src/utils/runs.js';

// Exercise the real hook with controlled hook slots and deferred API reads.
// No timer, browser, server, or added test dependency is needed for this race.
const source = (await readFile(new URL('../src/hooks/useSimulationData.js', import.meta.url), 'utf8'))
  .replace(/^import .*;\n/gm, '').replace('export function useSimulationData', 'function useSimulationData');
const tick = () => new Promise(resolve => setImmediate(resolve));
function world() {
  const slots = [], effects = [], requests = [];
  let cursor = 0, workspaceId = 'A', hook;
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
    apiClient: {getAgents: api('agents'), getTasks: api('tasks'), getMetrics: api('metrics')},
    useWorkspace: () => ({activeWorkspaceId: workspaceId}),
    useBackendConnection: () => 'connected', useLiveSocket: () => 'connected',
    mergeRuns, mergeActiveRuns, setInterval: () => 1, clearInterval() {},
  };
  hook = vm.runInNewContext(source + '\nuseSimulationData;', context);
  const render = (id = workspaceId, commit = true) => {
    workspaceId = id; cursor = 0; const result = hook();
    if (commit) {while (effects.length) effects.shift()();}
    return result;
  };
  const resolve = (id, title) => requests.filter(r => r.id === id && !r.done).forEach(r => {
    r.done = true; r.resolve(r.name === 'tasks' ? [{id: title, workspaceId: id}] : r.name === 'agents' ? [] : {summary: {}});
  });
  return {render, resolve, requests};
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
