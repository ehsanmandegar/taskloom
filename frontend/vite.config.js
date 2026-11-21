import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// Dev mode: Vite serves the UI and forwards API calls to the Taskloom backend (python main.py).
// Defaults: UI :5173, backend :8003. `TASKLOOM.bat dev 8004` sets TASKLOOM_PORT/TASKLOOM_UI_PORT so a second
// copy can run next to the first one.
const backendPort = Number(process.env.TASKLOOM_PORT) || 8003;
const uiPort = Number(process.env.TASKLOOM_UI_PORT) || 5173;

export default defineConfig({
  plugins: [react()],
  server: {port: uiPort, strictPort: true, open: true, proxy: {'/api': `http://localhost:${backendPort}`}},
});
