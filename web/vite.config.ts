import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em dev, /api vai pro uvicorn local; em produção quem roteia é o Caddy.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
