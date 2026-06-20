import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built app works under any /courses/<...>/ prefix in MinIO.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
