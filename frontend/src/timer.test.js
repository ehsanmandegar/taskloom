import assert from 'node:assert/strict';
import test from 'node:test';
import {formatTime} from './timer.js';

test('formats time with zero-padded milliseconds', () => {
  assert.equal(formatTime(new Date(2026, 0, 1, 7, 4, 9, 6)), '07:04:09.006');
});
