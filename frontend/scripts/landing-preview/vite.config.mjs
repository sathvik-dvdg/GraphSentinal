// Builds the landing preview on its own:
//   npx vite build -c scripts/landing-preview/vite.config.mjs
//   npx vite preview -c scripts/landing-preview/vite.config.mjs
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')

export default defineConfig({
  root,
  plugins: [react()],
  build: {
    outDir: resolve(root, 'dist/landing-preview'),
    emptyOutDir: true,
    rollupOptions: { input: resolve(root, 'scripts/landing-preview/index.html') },
  },
})
