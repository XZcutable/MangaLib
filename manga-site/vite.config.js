import { defineConfig } from "vite"
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { readFileSync } from "node:fs"

// Server and app share one version number, kept in package.json (and pyproject.toml)
const { version } = JSON.parse(readFileSync(path.resolve(__dirname, "package.json"), "utf8"))
const port = parseInt(process.env.PORT || "8443")

export default defineConfig(({ mode }) => ({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // Alias @ to the src directory
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // File types to support raw imports. Never add .css, .jsx, or .js files to this.
  assetsInclude: ["**/*.svg", "**/*.csv"],
  // Relative asset paths, resolved against the <base> tag the server sets, so one build works at / and
  // under a sub-path like /manga/
  base: "./",
  build: {
    sourcemap: mode === "development" ? "inline" : false,
    minify: mode !== "development",
  },
  server: {
    host: "0.0.0.0",
    port,
    strictPort: true,
    // Sends API calls to a local myMangaLib server during development, so no CORS setup is needed.
    // Set MANGALIB_SERVER to use a different one.
    proxy: {
      "/api": process.env.MANGALIB_SERVER || "http://127.0.0.1:5000",
    },
  },
  preview: {
    host: "0.0.0.0",
    port,
  },
}))
