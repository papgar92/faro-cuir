import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Este fichero lo ejecuta Node, no el navegador, así que `process` existe — pero el tsconfig del
// proyecto no incluye los tipos de Node y no se van a añadir por una línea. Se declara lo justo:
// una dependencia de desarrollo entera para tipar una variable de entorno sería peor cambio.
declare const process: { env: Record<string, string | undefined> };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // **Sondeo en vez de eventos del sistema de ficheros, y solo dentro de docker.**
    // Un `bind mount` desde Windows no entrega eventos inotify al contenedor Linux, así que el
    // servidor de desarrollo no se entera de los cambios: se editaba código, la web seguía
    // sirviendo lo anterior y parecía caché del navegador. Costó un rato el 2026-08-17.
    // Fuera de docker no se activa, porque sondear cuesta CPU y ahí los eventos funcionan.
    watch: process.env.VITE_POLLING ? { usePolling: true, interval: 400 } : undefined,
    // El dev server reenvía /api al backend en vez de que el navegador le hable directo.
    //
    // La alternativa sería activar CORS en FastAPI, y es peor: obligaría a relajar en el
    // backend una política de origen cruzado para resolver un problema que solo existe en
    // desarrollo, donde el frontend vive en el puerto 5173 y la API en el 8000. En producción
    // ambos irán tras el mismo origen y no hay nada que relajar. Con el proxy, la API puede
    // seguir sin ninguna cabecera CORS permisiva.
    proxy: {
      "/api": {
        // Fuera de docker, el backend está en el host y ahí el puerto es el **8010** (fijo desde
        // el 2026-09-04; el porqué está en `docker-compose.yml`, junto al mapeo). Dentro del
        // contenedor de desarrollo, 127.0.0.1 sería el propio contenedor, así que el destino
        // llega por entorno (`VITE_API_PROXY=http://backend:8000` en el compose) y ahí sigue
        // siendo el 8000, porque eso es red de contenedores y no toca el host.
        //
        // Este valor por defecto y el mapeo del compose son los dos únicos sitios del
        // repositorio que hablan del puerto del host: si se mueve, se mueve en los dos.
        target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8010",
        changeOrigin: true,
      },
    },
  },
});
