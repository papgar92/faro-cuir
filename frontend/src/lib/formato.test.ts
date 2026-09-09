import { describe, expect, it } from "vitest";
import { acortarHash, formatearFecha, formatearSelloTiempo } from "./formato";

/**
 * El formateo, que parece inofensivo y ya publicó una fecha inventada.
 *
 * El comentario de `formatearFecha` lo cuenta: la función recibe las dos formas —una fecha suelta
 * (`2014-11-06`) y un instante completo (`2026-08-21T20:50:00Z`)— y sin recortar la segunda, la
 * pantalla publicaba **«el NaN ago 2026»**. Se vio en el navegador el 2026-08-22, no por ningún
 * test. Esto es ese test.
 */

describe("formatearFecha", () => {
  it("una fecha de publicación se lee en castellano", () => {
    expect(formatearFecha("2024-12-19")).toBe("19 dic 2024");
  });

  it("un instante completo NO produce «NaN», que es el bug que existió", () => {
    expect(formatearFecha("2026-08-21T20:50:00Z")).toBe("21 ago 2026");
  });

  it("no aplica zona horaria: un boletín se publica un día del calendario, no a una hora", () => {
    // Con `new Date(iso)` el 1 de enero se interpretaría como medianoche UTC y en España
    // podría retroceder al 31 de diciembre. Ese es el motivo de partir la cadena a mano.
    expect(formatearFecha("2025-01-01")).toBe("1 ene 2025");
  });

  it.each(["", "no es una fecha", "2024-13-40"])(
    "devuelve la entrada tal cual si no la entiende: %s",
    (entrada) => {
      // Falla enseñando el dato crudo, no inventando uno. Regla de oro 8.
      expect(formatearFecha(entrada)).toBe(entrada);
    },
  );
});

describe("formatearSelloTiempo", () => {
  it("el sello se enseña en UTC a propósito", () => {
    // Es un dato de verificación (6.5): quien compare nuestro archivo con el suyo necesita
    // leer el mismo valor esté donde esté, no uno traducido a su zona.
    expect(formatearSelloTiempo("2026-09-05T10:25:37Z")).toBe("2026-09-05 10:25:37Z");
  });

  it("un sello ilegible se enseña crudo en vez de como una fecha falsa", () => {
    expect(formatearSelloTiempo("cualquier cosa")).toBe("cualquier cosa");
  });
});

describe("acortarHash", () => {
  it("deja principio y final, que es lo que permite cotejar de un vistazo", () => {
    const sha = "4c485cb1d3aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa9dcfe1";
    expect(acortarHash(sha)).toBe("4c485cb1d3…9dcfe1");
  });

  it("no recorta lo que ya es corto, para no inventar unos puntos suspensivos", () => {
    expect(acortarHash("abc123")).toBe("abc123");
  });
});
