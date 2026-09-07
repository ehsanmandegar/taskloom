import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
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

test('dark theme exposes and uses the phosphor-green hacker accent', () => {
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(styles, /html\[data-theme="dark"\]\{--hacker-green:#00ff88;/);
  assert.match(styles, /html\[data-theme="dark"\] \.primary[^}]*var\(--hacker-green\)/);
  assert.match(styles, /body:after\{[^}]*repeating-linear-gradient/);
  assert.match(styles, /html\[data-theme="dark"\] pre\{[^}]*font-family:"Cascadia Code",Consolas,monospace/);
});
