import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on port 3000 to match the backend's CORS allow-list (config.py).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
  },
});
