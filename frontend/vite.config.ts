import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In Docker the backend is reachable as http://backend:8000 (set by docker-compose).
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": apiTarget } },
});
