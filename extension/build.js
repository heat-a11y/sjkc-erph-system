// esbuild build script — bundles TypeScript → JS for Chrome extension
const { build } = require("esbuild");
const path = require("path");

const entries = [
  { entry: "src/background.ts", outfile: "dist/background.js" },
  { entry: "src/content.ts", outfile: "dist/content.js" },
  { entry: "popup/popup.ts", outfile: "popup/popup.js" },
  { entry: "options/options.ts", outfile: "options/options.js" },
];

async function main() {
  for (const { entry, outfile } of entries) {
    await build({
      entryPoints: [path.join(__dirname, entry)],
      bundle: true,
      format: "iife",
      outfile: path.join(__dirname, outfile),
      minify: true,
      drop: ["console", "debugger"],
      loader: { ".ts": "tsx" },
    });
    console.log(`✓ Built ${entry} → ${outfile}`);
  }
  console.log("Build complete.");
}

(async () => {
  try {
    await main();
  } catch (e) {
    console.error(e);
    process.exit(1);
  }
})();
