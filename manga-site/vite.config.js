import { defineConfig } from "vite"
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { VitePWA } from "vite-plugin-pwa"
import { readFileSync } from "node:fs"

// Server and app share one version number, kept in package.json (and pyproject.toml)
const { version } = JSON.parse(readFileSync(path.resolve(__dirname, "package.json"), "utf8"))
const port = parseInt(process.env.PORT || "8443")

export default defineConfig(({ mode }) => ({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [
    react(),
    tailwindcss(),
    // Installable web app: manifest.webmanifest and the service worker in src/sw.js (registered by
    // lib/pwa.js, never in the Android app). The server fills in the owner's site name (frontend.py).
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      injectRegister: false,
      manifestFilename: "manifest.webmanifest",
      // Browsers fetch the manifest without cookies unless told to. Behind a login proxy (Cloudflare
      // Access) that gets the login page instead, and the app can't be installed.
      useCredentials: true,
      // Relative URLs follow the path the server is reached at, so one build works under /manga/ too
      manifest: {
        name: "myMangaLib",
        short_name: "myMangaLib",
        description: "Read the manga on your myMangaLib server.",
        start_url: "./",
        scope: "./",
        id: "./",
        display: "standalone",
        background_color: "#300c4c",
        theme_color: "#300c4c",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,png,webp,svg,woff2}"],
        // The worker never stores itself
        globIgnores: ["sw.js"],
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
      },
    }),
  ],
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
