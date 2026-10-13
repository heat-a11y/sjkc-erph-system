import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "happy-dom",
    globals: true,
    include: ["test/**/*.test.ts"],
    deps: { inline: [/\.\/src\//] },
  },
  resolve: {
    alias: {
      "../shared": "/home/school/Work/shared",
    },
  },
});
