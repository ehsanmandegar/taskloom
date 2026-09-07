import assert from 'node:assert/strict';
import test from 'node:test';
import {getInitialTheme, nextTheme} from './theme.js';

test('uses a saved valid theme before the system preference', () => {
  assert.equal(getInitialTheme({getItem: () => 'light'}, true), 'light');
});

test('falls back to the system preference when no theme is saved', () => {
  assert.equal(getInitialTheme({getItem: () => null}, true), 'dark');
  assert.equal(getInitialTheme({getItem: () => null}, false), 'light');
});

test('toggles between light and dark themes', () => {
  assert.equal(nextTheme('light'), 'dark');
  assert.equal(nextTheme('dark'), 'light');
});
