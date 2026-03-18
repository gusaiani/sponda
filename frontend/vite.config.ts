import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

function devFavicon(): Plugin {
  return {
    name: "dev-favicon",
    transformIndexHtml(html, ctx) {
      if (ctx.server) {
        // Swap at serve-time for Vite dev server, plus add a runtime
        // fallback so the dev favicon also shows on any localhost port
        // (e.g. Django serving the built HTML on 8710).
        return html.replace("/favicon.svg", "/favicon-dev.svg");
      }
      // Production build: swap favicon at runtime when on localhost
      return html.replace(
        "</head>",
        `<script>if(location.hostname==="localhost"||location.hostname==="127.0.0.1"){document.querySelector('link[rel="icon"]').href="/favicon-dev.svg"}</script>\n</head>`,
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), devFavicon()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8710",
        changeOrigin: true,
      },
    },
  },
});
