import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 配置说明见 https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5176',
        changeOrigin: true,
      }
    }
  }
})

