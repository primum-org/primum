import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

const root = (path: string) => fileURLToPath(new URL(path, import.meta.url));
// Where a service runs while the UI is being worked on: `just dev`.
const SERVICE = process.env.PRIMUM_SERVICE ?? "http://127.0.0.1:8080";

export default defineConfig({
  // Relative: the runtime serves the build under /app/ for now, and at / from block 5.3.
  base: "./",
  plugins: [vue()],
  resolve: {
    alias: {
      "@": root("./src"),
      // The single sources of texts and of the brand: never copied into this app.
      "@i18n": root("../../i18n"),
      "@design": root("../../design"),
    },
  },
  build: {
    // Inside the runtime's package, which serves it; kept out of git and built when deploying.
    outDir: root("../../packages/runtime/src/primum_runtime/webui"),
    emptyOutDir: true,
  },
  server: {
    // The host header is left as the browser sent it: the service refuses a request whose
    // Origin is not its own page's.
    proxy: { "/api": { target: SERVICE, ws: true } },
    // The texts and the brand live outside this folder, at the repository's root.
    fs: { allow: [root("."), root("../../i18n"), root("../../design")] },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
