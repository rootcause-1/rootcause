import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// RC_API points the dev server at any RootCause API, e.g. RC_API=http://3.234.90.242 to style against the replay site
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: process.env.RC_API ?? "http://localhost:8000", changeOrigin: true } } },
  build: { chunkSizeWarningLimit: 1600 },
});
