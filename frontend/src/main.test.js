import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

test('does not show the removed delivery heading', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.doesNotMatch(source, /از درخواست تا برنچ آماده‌ی تحویل/);
});

test('offers merge request creation only after push and links the result', () => {
  const source = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.match(source, /action\('merge-request'\)/);
  assert.match(source, /disabled=\{!task\.pushed\|\|!!task\.merge_request_url\|\|busy\}/);
  assert.match(source, /href=\{task\.merge_request_url\}/);
});
