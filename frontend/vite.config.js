import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// Dev mode: Vite serves the UI on :5173 and forwards API calls to the Taskloom backend (python main.py, :8003).
export default defineConfig({
  plugins: [react()],
  server: {port: 5173, open: true, proxy: {'/api': 'http://localhost:8003'}},
});
