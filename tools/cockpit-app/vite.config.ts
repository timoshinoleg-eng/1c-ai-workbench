import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite is the dev server that Tauri loads the webview from.
// Port 1420 is the Tauri 2.x convention; do not change without updating
// tauri.conf.json -> build.devUrl and capabilities/default.json.
//
// Note: test configuration is in vitest.config.ts (separate file).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: "127.0.0.1",
    hmr: {
      protocol: "ws",
      host: "127.0.0.1",
      port: 1421,
    },
    watch: {
      // Don't watch the Rust side from Vite; tauri-cli owns that lifecycle.
      ignored: ["**/src-tauri/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_ENV_*"],
  build: {
    target: "es2022",
    minify: "esbuild",
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
    outDir: "dist",
  },
});
