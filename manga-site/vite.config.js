import { defineConfig } from "vite"
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { readFileSync } from "node:fs"

// Server and app share one version number, kept in package.json (and pyproject.toml)
const { version } = JSON.parse(readFileSync(path.resolve(__dirname, "package.json"), "utf8"))

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // File types to support raw imports. Never add .css, .jsx, or .js files to this.
  assetsInclude: ["**/*.svg", "**/*.csv"],
  server: {
    // Sends API calls to a local myMangaLib server during development, so no CORS setup is needed.
    // Set MANGALIB_SERVER to use a different one.
    proxy: {
      "/api": process.env.MANGALIB_SERVER || "http://127.0.0.1:5000",
    },
  },
})
