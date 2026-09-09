import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_BASE || 'http://127.0.0.1:8000'

  // All API paths that the frontend fetches
  const proxyPaths = ['/auth', '/chat', '/cart', '/addresses', '/orders', '/mcp']

  const proxyConfig = {}
  for (const path of proxyPaths) {
    proxyConfig[path] = {
      target: apiTarget,
      changeOrigin: true,
      secure: false,
    }
  }

  return {
    plugins: [react()],
    server: {
      port: 5174,
      proxy: proxyConfig,
    },
  }
})
