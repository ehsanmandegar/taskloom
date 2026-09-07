export const THEMES = {light: 'light', dark: 'dark'};

export function getInitialTheme(storage, prefersDark = false) {
  const saved = storage?.getItem('taskloom-theme');
  if (saved === THEMES.light || saved === THEMES.dark) return saved;
  return prefersDark ? THEMES.dark : THEMES.light;
}

export function nextTheme(theme) {
  return theme === THEMES.dark ? THEMES.light : THEMES.dark;
}
