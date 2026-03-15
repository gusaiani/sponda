import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

function devFavicon(): Plugin {
  return {
    name: "dev-favicon",
    transformIndexHtml(html, ctx) {
      if (ctx.server) {
        return html.replace("/favicon.svg", "/favicon-dev.svg");
      }
      return html;
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
