/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// The FastAPI backend serves the built app from the same origin in production, so the
// API client uses relative paths. In dev (Vite :5173, API :8000) we proxy the API
// routes to the backend.
const API_ROUTES = ["/applicants", "/score", "/validate", "/health"];

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      API_ROUTES.map((route) => [route, { target: "http://localhost:8000", changeOrigin: true }]),
    ),
  },
  build: { outDir: "dist" },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
