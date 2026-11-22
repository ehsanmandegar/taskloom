import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {AUTONOMY_OPTIONS, EMPTY_FORM, MAX_IDEA, STACK_OPTIONS, buildRequestBody, ideaProblem, stageSummary} from './project_builder.js';

test('a description must be between 10 and 4000 characters', () => {
  assert.notEqual(ideaProblem(''), '');
  assert.notEqual(ideaProblem('کوتاه'), '');
  assert.equal(ideaProblem('یک فروشگاه آنلاین برای کتاب'), '');
  assert.notEqual(ideaProblem('x'.repeat(MAX_IDEA + 1)), '');
  assert.notEqual(ideaProblem('   short   '), '');
});

test('the request body trims text and leaves empty optional fields out', () => {
  const body = buildRequestBody({...EMPTY_FORM, idea: '  A bookshop API with a cart  ', name: ' ', baseDir: ''}, false);
  assert.deepEqual(body, {idea: 'A bookshop API with a cart', stack: 'auto', autonomy: 'balanced', use_ai: true, preview: false});
  const full = buildRequestBody({idea: 'A bookshop API', name: ' Book Shop ', stack: 'node', autonomy: 'manual', useAi: false, baseDir: ' D:\\work '}, true);
  assert.deepEqual(full, {idea: 'A bookshop API', stack: 'node', autonomy: 'manual', use_ai: false, preview: true, name: 'Book Shop', base_dir: 'D:\\work'});
});

test('options match what the server accepts and the safe preset is the default', () => {
  assert.deepEqual(STACK_OPTIONS.map(option => option.value), ['auto', 'python', 'node', 'web']);
  assert.deepEqual(AUTONOMY_OPTIONS.map(option => option.value), ['manual', 'balanced', 'autopilot']);
  assert.equal(EMPTY_FORM.autonomy, 'balanced');
  assert.match(AUTONOMY_OPTIONS[2].hint, /sandbox/);
  assert.match(stageSummary({stage: 'backend', files: ['a', 'b']}), /^backend — /);
});

test('the builder is wired into the projects page and posts to the builder endpoint', () => {
  const dashboard = readFileSync(new URL('./sdlc_dashboard.jsx', import.meta.url), 'utf8');
  assert.match(dashboard, /import ProjectBuilder from '\.\/project_builder\.jsx'/);
  assert.match(dashboard, /<ProjectBuilder onCreated=/);
  const form = readFileSync(new URL('./project_builder.jsx', import.meta.url), 'utf8');
  assert.match(form, /\/api\/sdlc\/project-builder/);
  assert.match(form, /ساخت خودکار پروژه/);
});
