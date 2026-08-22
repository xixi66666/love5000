import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'src/main/frontend',
  base: '/',
  plugins: [react()],
  build: {
    outDir: '../resources/static',
    emptyOutDir: false,
    sourcemap: false
  }
});
