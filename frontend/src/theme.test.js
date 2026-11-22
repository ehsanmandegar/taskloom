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

test('light and dark both come from the Radix Themes tokens, not hand-written per-theme rules', () => {
  const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');
  const main = readFileSync(new URL('./main.jsx', import.meta.url), 'utf8');

  assert.doesNotMatch(styles, /html\[data-theme="dark"\]/);        // no hand-written dark overrides left
  assert.match(styles, /var\(--gray-6\)/);                           // colours are theme tokens
  assert.match(main, /<Theme [^>]*appearance=\{theme\}/);            // the saved theme drives the Radix appearance
  assert.match(main, /@radix-ui\/themes\/styles\.css/);
  assert.match(main, /<DirectionProvider dir="rtl">/);                // Radix primitives follow the RTL layout
});

test('modals and confirmations use the shared accessible dialogs instead of window.confirm/prompt', () => {
  for (const file of ['main.jsx', 'sdlc_dashboard.jsx', 'release_management.jsx']) {
    const source = readFileSync(new URL(`./${file}`, import.meta.url), 'utf8');
    assert.doesNotMatch(source, /window\.(confirm|prompt|alert)\(/, file);
  }
  const sdlc = readFileSync(new URL('./sdlc_dashboard.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(sdlc, /className="sdlc-modal-overlay"/);        // hand-made overlays replaced by <ModalShell>
  assert.match(sdlc, /<ModalShell /);
});
