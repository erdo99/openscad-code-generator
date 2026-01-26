import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5002',  // io_net backend port (test için)
        // target: 'http://localhost:5001',  // Improved backend port
        changeOrigin: true
      }
    }
  }
})
