import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em dev, /api vai pro uvicorn local (API_PORT troca a porta); em produção quem roteia é o Caddy.
const apiPort = process.env.API_PORT ?? '8000'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': `http://localhost:${apiPort}` } },
})
