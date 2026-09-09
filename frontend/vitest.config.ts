import { defineConfig } from "vitest/config";

/**
 * Configuracion de los tests del frontend. ADR 0033 / CI del 2026-09-05.
 *
 * `jsdom` y no el entorno de node: `navigation.ts` lee `window.location` y escribe en
 * `window.history`, que es justo lo que hay que poder probar. No se montan componentes de React
 * todavia -- eso pide `@testing-library/react` y es otra dependencia-- asi que por ahora lo que
 * se cubre es la LOGICA: la que decide que se pide a la API, que se escribe en la URL y como se
 * presenta un dato de verificacion.
 *
 * Empezar por ahi no es pereza: son las funciones donde un error es invisible en pantalla. El
 * `NaN ago 2026` de `formatearFecha` y el filtro que escondia las normas en `sospecha` son los
 * dos bugs reales que este directorio ha tenido, y los dos vivian en logica pura.
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
