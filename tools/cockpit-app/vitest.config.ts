/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx", "src/**/*.test.ts", "src/**/*.test.tsx"],
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**", "src-tauri/**"],
  },
});
