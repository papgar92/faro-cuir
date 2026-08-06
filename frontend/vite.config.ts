import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // El dev server reenvía /api al backend en vez de que el navegador le hable directo.
    //
    // La alternativa sería activar CORS en FastAPI, y es peor: obligaría a relajar en el
    // backend una política de origen cruzado para resolver un problema que solo existe en
    // desarrollo, donde el frontend vive en el puerto 5173 y la API en el 8000. En producción
    // ambos irán tras el mismo origen y no hay nada que relajar. Con el proxy, la API puede
    // seguir sin ninguna cabecera CORS permisiva.
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
