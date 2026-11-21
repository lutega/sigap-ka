// Konfigurasi Vite untuk konsol SIGAP-KA.
// Lapis: A (antarmuka). Saat pengembangan, permintaan API diteruskan ke FastAPI (port 8765,
// dapat diganti dengan variabel lingkungan SIGAP_API). Saat produksi, hasil build disajikan
// FastAPI dari origin yang sama sehingga URL relatif tetap berlaku.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = process.env.SIGAP_API || "http://127.0.0.1:8765";
const JALUR_API = ["/auth", "/pengguna", "/data", "/info", "/episode", "/tindakan", "/kurva", "/simulasi", "/demo", "/kesehatan"];

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 800 }, // Recharts membuat bundel tunggal sekitar 590 kB
  server: {
    port: 5173,
    proxy: Object.fromEntries(JALUR_API.map((j) => [j, { target: API, changeOrigin: true }])),
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.js"],
  },
});
