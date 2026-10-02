import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks only to Vite; /api is proxied to FastAPI so cookies are same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8000" },
  },
});
