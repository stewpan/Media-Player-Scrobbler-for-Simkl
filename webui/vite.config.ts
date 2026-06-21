import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build straight into the Python package so the embedded Flask server can serve it.
// Relative base keeps asset URLs working regardless of how the server mounts them.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../simkl_mps/web/dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:5555",
    },
  },
});
