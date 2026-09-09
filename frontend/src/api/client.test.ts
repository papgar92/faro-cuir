import { describe, expect, it } from "vitest";
import { type EstadoPrefiltro, entraEnLaCola } from "./client";

/**
 * `entraEnLaCola` es un espejo de `EstadoPrefiltro.entra_en_la_cola_del_extractor` del backend,
 * y existe por un motivo escrito en su propio comentario: **para que la cola no se escriba nunca
 * como `=== "relevante"`**.
 *
 * Ese error ya se cometió una vez, y se cometió en una pantalla: el filtro «solo las que entran
 * en la cola» del Archivo comparaba con `"relevante"` y **escondía las normas en `sospecha`**,
 * que son justamente las que el prefiltro NO ha sabido descartar. Esconder esas es el falso
 * negativo que este proyecto no se permite (7.1), y no lo habría visto ningún test de interfaz.
 */

describe("entraEnLaCola", () => {
  it("`sospecha` entra en la cola, y ese es todo el sentido de esta función", () => {
    expect(entraEnLaCola("sospecha")).toBe(true);
  });

  it("`relevante` entra", () => {
    expect(entraEnLaCola("relevante")).toBe(true);
  });

  it.each<[EstadoPrefiltro, string]>([
    ["descartada", "descartada tras leer su texto completo"],
    ["pendiente", "aún no evaluada; volverá sola"],
    // `ilegible` es el caso fino: NO entra en las colas automáticas, pero tampoco es un
    // descarte -- habla de nosotros, no de la norma (ADR 0020). Aquí solo se fija que no
    // se cuela en la cola del extractor.
    ["ilegible", "archivada y no parseable: trabajo para una persona"],
  ])("`%s` no entra (%s)", (estado) => {
    expect(entraEnLaCola(estado)).toBe(false);
  });

  it("los cinco estados están cubiertos, para que añadir uno rompa este test", () => {
    // Si mañana aparece un sexto estado, alguien tiene que decidir a conciencia si entra en
    // la cola. Este test es lo que obliga a esa decisión en vez de dejarla al valor por defecto.
    const todos: EstadoPrefiltro[] = [
      "pendiente",
      "sospecha",
      "relevante",
      "descartada",
      "ilegible",
    ];
    expect(todos.filter(entraEnLaCola)).toEqual(["sospecha", "relevante"]);
  });
});
