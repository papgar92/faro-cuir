import { describe, expect, it, vi } from "vitest";
import { escribirUrl, leerUrl } from "./navigation";

/**
 * La navegación por URL, que desde el 2026-09-05 lleva **ids que vienen de fuera**.
 *
 * Lo que se prueba aquí no es que `URLSearchParams` funcione. Son las dos propiedades que
 * sostienen decisiones del proyecto y que un refactor puede romper sin que se note:
 *
 * 1. **Un valor de la barra de direcciones no se compone con nada sin validarlo.** Es la
 *    sección 6.10 aplicada a la URL: `doc` acaba en `GET /api/documentos/{id}`, así que lo
 *    que no sea un id se descarta aquí y no llega a formar una petición.
 * 2. **Una norma sin su documento no se escribe.** La API expone las normas anidadas dentro
 *    de su documento, así que `?norma=123` a secas es un enlace que nadie puede resolver, y
 *    publicar un enlace roto es peor que no publicarlo.
 */

/**
 * Espía `history.replaceState` para poder leer lo que se escribió sin navegar de verdad.
 *
 * Sin anotación de tipo a propósito: se infiere del `spyOn` y así no hay dos verdades que
 * mantener. La primera versión ponía `: string` —un despiste— y `vitest` lo dio por bueno porque
 * **no comprueba tipos**; lo cazó `tsc` en el CI, en el mismo commit que lo añadía.
 */
function urlEscrita() {
  return vi.spyOn(window.history, "replaceState").mockImplementation(() => {});
}

describe("leerUrl", () => {
  it("una pantalla que no existe cae al mapa en vez de fallar", () => {
    // Un enlace viejo o mal copiado tiene que aterrizar en algún sitio, no romper la web.
    expect(leerUrl("?pantalla=inventada").screen).toBe("mapa");
    expect(leerUrl("").screen).toBe("mapa");
  });

  it("lee la pantalla, la comunidad y la norma abierta", () => {
    const estado = leerUrl("?pantalla=archivo&ccaa=AN&doc=84448&norma=83259");
    expect(estado).toEqual({ screen: "archivo", ccaa: "AN", doc: 84448, norma: 83259 });
  });

  it("`ficha` ya no es una pantalla y no revive por un enlace viejo", () => {
    // Se retiró al fusionarla con el Archivo. Un enlace guardado de antes cae al mapa.
    expect(leerUrl("?pantalla=ficha").screen).toBe("mapa");
  });

  it.each([
    ["texto", "?doc=hola"],
    ["negativo", "?doc=-3"],
    ["cero", "?doc=0"],
    ["decimal", "?doc=1.5"],
    ["inyección de ruta", "?doc=../../etc/passwd"],
    ["desbordamiento", "?doc=99999999999999999999"],
    ["vacío", "?doc="],
  ])("descarta un id que no es un id: %s", (_caso, busqueda) => {
    // No se "arregla" ni se recorta: se ignora. Arreglar un valor que viene de fuera es
    // exactamente como se acaba pidiendo algo que no era.
    expect(leerUrl(busqueda).doc).toBeUndefined();
  });
});

describe("escribirUrl", () => {
  it("no escribe una norma sin su documento", () => {
    // `?norma=83259` a secas no identifica nada: la API pide el documento y busca la norma
    // dentro. Se omite en vez de publicar un enlace que no se puede resolver.
    const espia = urlEscrita();
    escribirUrl({ screen: "archivo", norma: 83259 });
    expect(espia.mock.calls[0]?.[2]).not.toContain("norma");
    espia.mockRestore();
  });

  it("escribe documento y norma juntos, que es lo que hace enlazable una norma", () => {
    const espia = urlEscrita();
    escribirUrl({ screen: "archivo", doc: 84448, norma: 83259 });
    const escrita = String(espia.mock.calls[0]?.[2]);
    expect(escrita).toContain("doc=84448");
    expect(escrita).toContain("norma=83259");
    espia.mockRestore();
  });

  it("no escribe `pantalla=mapa`, que es el valor por defecto", () => {
    // `?pantalla=mapa` en la barra de direcciones es ruido que no dice nada.
    const espia = urlEscrita();
    escribirUrl({ screen: "mapa" });
    expect(String(espia.mock.calls[0]?.[2])).not.toContain("pantalla");
    espia.mockRestore();
  });

  it("lo que escribe se puede volver a leer", () => {
    // La propiedad que de verdad importa: un enlace compartido lleva a donde decía.
    const espia = urlEscrita();
    const original = { screen: "archivo" as const, ccaa: "CT", doc: 84448, norma: 83259 };
    escribirUrl(original);
    expect(leerUrl(String(espia.mock.calls[0]?.[2]))).toEqual(original);
    espia.mockRestore();
  });
});
