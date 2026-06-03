import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("@react-three/fiber")) {
            return "three-fiber";
          }
          if (id.includes("@react-three/drei")) {
            return "three-drei";
          }
          if (id.includes("/three/")) {
            return "three-core";
          }
          if (id.includes("animejs") || id.includes("lenis")) {
            return "motion-core";
          }
          if (id.includes("react-router-dom")) {
            return "router";
          }
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/metrics": "http://127.0.0.1:8000",
      "/snapshots": "http://127.0.0.1:8000",
      "/audits": "http://127.0.0.1:8000",
      "/jobs": "http://127.0.0.1:8000",
      "/workers": "http://127.0.0.1:8000",
      "/maintenance": "http://127.0.0.1:8000",
      "/analytics": "http://127.0.0.1:8000",
      "/control-plane-alerts": "http://127.0.0.1:8000",
      "/remediation-reports": "http://127.0.0.1:8000"
    }
  }
});
