import process from 'node:process'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  if (mode === 'production') {
    const apiUrl = (env.VITE_API_URL || process.env.VITE_API_URL || '').trim()
    const allowLocalBypass = process.env.VITE_ALLOW_LOCAL_BUILD === 'true'

    if (!allowLocalBypass) {
      if (!apiUrl) {
        throw new Error(
          '🚨 [VISION-BALLING BUILD ERROR] VITE_API_URL is required for production builds. ' +
          'Configure VITE_API_URL in Cloudflare Pages environment variables (e.g. https://<project>.up.railway.app). ' +
          'Silent localhost fallback is forbidden in production.'
        )
      }
      if (apiUrl.includes('localhost') || apiUrl.includes('127.0.0.1')) {
        throw new Error(
          `🚨 [VISION-BALLING BUILD ERROR] VITE_API_URL cannot point to localhost in production ('${apiUrl}'). ` +
          'Provide the production HTTPS API URL.'
        )
      }
    }
  }

  return {
    plugins: [react()],
  }
})
