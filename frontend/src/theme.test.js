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

test('dark theme uses Telegram blue surfaces and accent', () => {
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

  assert.match(styles, /html\[data-theme="dark"\]\{--hacker-green:#5288c1;/);
  assert.match(styles, /--tg-surface:#17212b;--tg-raised:#1e2c3a;/);
  assert.match(styles, /html\[data-theme="dark"\] body:before,html\[data-theme="dark"\] body:after\{display:none\}/);
  assert.match(styles, /html\[data-theme="dark"\] \.primary[^}]*background:#5288c1/);
});
