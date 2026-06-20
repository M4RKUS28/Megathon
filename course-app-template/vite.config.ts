import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Per-course apps are hosted under a versioned MinIO prefix and embedded via
// iframe, so all asset URLs must be relative.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
