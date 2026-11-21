import assert from 'node:assert/strict';
import test from 'node:test';
import {
  adminHeaders, createBlocker, filterTasks, gitIntegrationSummary, hasBusyRelease, isValidVersion, pruneSelection,
  releaseActions, releaseStatusLabel, releaseStatusTone, toggleSelection,
} from './releases.js';

const rows = [
  {task_id: 'DWS-99', workflow: 'DWS', title: 'Login page', status: 'done', branch: 'DWS-99', eligible: true},
  {task_id: 'DWS-100', workflow: 'DWS', title: 'Cart', status: 'done', branch: 'DWS-100', eligible: false},
  {task_id: 'SDLC-1001', workflow: 'SDLC', title: 'Checkout API', status: 'done', branch: 'SDLC-1001', eligible: true},
];

test('accepts only semantic-looking versions', () => {
  for (const ok of ['1.0.1', '10.20.30', '1.0.0-rc.1', ' 2.0.0 ']) assert.equal(isValidVersion(ok), true, ok);
  for (const bad of ['1.0', 'v1.0.0', '', '1.0.0; rm', '1.0.x']) assert.equal(isValidVersion(bad), false, bad);
});

test('filters tasks by text, workflow, status and eligibility', () => {
  assert.deepEqual(filterTasks(rows, {q: 'dws-1'}).map(r => r.task_id), ['DWS-100']);
  assert.deepEqual(filterTasks(rows, {q: 'checkout'}).map(r => r.task_id), ['SDLC-1001']);
  assert.deepEqual(filterTasks(rows, {workflow: 'SDLC'}).map(r => r.task_id), ['SDLC-1001']);
  assert.deepEqual(filterTasks(rows, {eligibleOnly: true}).map(r => r.task_id), ['DWS-99', 'SDLC-1001']);
  assert.equal(filterTasks(rows, {status: 'failed'}).length, 0);
  assert.equal(filterTasks(null).length, 0);
});

test('selection toggles and drops tasks that stopped being eligible', () => {
  let selected = toggleSelection([], 'DWS-99');
  selected = toggleSelection(selected, 'DWS-100');
  assert.deepEqual(selected, ['DWS-99', 'DWS-100']);
  assert.deepEqual(toggleSelection(selected, 'DWS-99'), ['DWS-100']);
  assert.deepEqual(pruneSelection(selected, rows), ['DWS-99']);
});

test('create button explains what is missing', () => {
  assert.match(createBlocker({repositoryId: '', version: '1.0.0', selected: ['a']}), /مخزن/);
  assert.match(createBlocker({repositoryId: 'r', version: '1.0', selected: ['a']}), /1\.0\.1/);
  assert.match(createBlocker({repositoryId: 'r', version: '1.0.0', selected: []}), /تسک/);
  assert.equal(createBlocker({repositoryId: 'r', version: '1.0.0', selected: ['a']}), '');
});

test('release actions follow the status', () => {
  assert.deepEqual(releaseActions({status: 'waiting_approval'}), {start: false, approve: true, retry: false, rebuild: true, cancel: true});
  assert.equal(releaseActions({status: 'released'}).approve, false);
  assert.equal(releaseActions({status: 'released'}).cancel, false);
  assert.equal(releaseActions({status: 'merging'}).cancel, false);
  assert.equal(releaseActions({status: 'failed'}).retry, true);
  assert.equal(releaseActions({status: 'draft'}).start, true);
});

test('status labels, tones and polling', () => {
  assert.equal(releaseStatusTone('released'), 'green');
  assert.equal(releaseStatusTone('failed'), 'red');
  assert.equal(releaseStatusTone('???'), 'gray');
  assert.equal(releaseStatusLabel('???'), '???');
  assert.equal(hasBusyRelease([{status: 'released'}, {status: 'testing'}]), true);
  assert.equal(hasBusyRelease([{status: 'released'}, {status: 'waiting_approval'}]), false);
});

test('admin headers only carry what was entered', () => {
  assert.deepEqual(adminHeaders('', ''), {'Content-Type': 'application/json'});
  assert.deepEqual(adminHeaders(' tok ', 'ann'), {'Content-Type': 'application/json', 'X-Taskloom-Admin-Token': 'tok', 'X-Taskloom-User': 'ann'});
});

test('git integration summary', () => {
  assert.equal(gitIntegrationSummary({merged_into_develop: true}).tone, 'green');
  assert.equal(gitIntegrationSummary({status: 'conflict'}).tone, 'red');
  assert.equal(gitIntegrationSummary(null).tone, 'gray');
});
