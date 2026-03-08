import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@tanstack/react-query': path.resolve(__dirname, './src/shims/react-query.tsx'),
      axios: path.resolve(__dirname, './src/shims/axios.ts'),
      'lucide-react': path.resolve(__dirname, './src/shims/lucide-react.tsx'),
    },
  },
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
