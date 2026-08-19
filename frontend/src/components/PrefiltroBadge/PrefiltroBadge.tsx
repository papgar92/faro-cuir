import type { EjePrefiltro, EstadoPrefiltro } from "../../api/client";

/**
 * Estado del prefiltro léxico de una norma (ADR 0007).
 *
 * Color + glifo + texto, nunca solo color, igual que `ClassificationBadge`. Y ojo con no
 * confundirlo con aquél: esto **no es una clasificación**. Decir que una norma es "relevante"
 * aquí solo significa que su título contiene vocabulario del proyecto y que por eso se
 * mirará; no dice absolutamente nada sobre si avanza o retrocede en derechos. Por eso usa
 * gris neutro y no la paleta de avance/retroceso.
 */
const META: Record<
  EstadoPrefiltro,
  { etiqueta: string; glifo: string; clases: string; pista?: string }
> = {
  relevante: {
    etiqueta: "Pasa el prefiltro",
    glifo: "◉",
    clases: "border-ink-3 bg-surface-2 text-ink",
  },
  // Cuarto estado (7.2). Entra en la cola del extractor **igual que `relevante`**: la
  // diferencia es de turno, no de cobertura, y por eso se pinta como un peldaño intermedio y
  // no como un descarte suave. Que se lea "entra en la cola" y no "dudosa" es deliberado —
  // "dudosa" invita a ignorarla, y el proyecto entero existe para no ignorar estas.
  sospecha: {
    etiqueta: "Entra en la cola",
    glifo: "◐",
    clases: "border-line-2 bg-inset text-ink-2",
  },
  descartada: {
    etiqueta: "Descartada",
    glifo: "○",
    clases: "border-line-2 text-ink-3",
  },
  pendiente: {
    etiqueta: "Sin evaluar",
    glifo: "◌",
    clases: "border-dashed border-line-2 text-ink-3",
  },
  // Quinto estado (ADR 0020), y el único de los cinco que sale del gris neutro. No contradice
  // la nota de arriba —esto sigue sin ser una clasificación— porque lo que señala no es la
  // norma: es un fallo de cobertura **nuestro**, y este es el único sitio de la interfaz donde
  // ese fallo se ve. Dejarlo en el gris del descarte lo haría igual de invisible que estaba
  // dentro de `pendiente`, que es justo el problema que el ADR arregla.
  //
  // Usa la paleta de **alerta** y no la de retroceso a propósito: `reg` significa "esta norma
  // recorta un derecho", y esta insignia no afirma nada sobre el contenido de la norma. Lo que
  // dice es "aquí no estamos mirando".
  //
  // «No se puede leer» y no «error»: dice qué pasa con esta norma, no que algo se haya roto al
  // cargar la página.
  ilegible: {
    etiqueta: "No se puede leer",
    glifo: "⊘",
    clases: "border-alr bg-alr-soft text-alr",
    // La pista importa porque lo siguiente que se ve en la insignia son los términos, y sin
    // esto se leerían como términos del texto. Salen del título, que es lo único legible.
    pista:
      "Su texto está descargado y archivado, pero el pipeline no puede parsearlo: no hay " +
      "vigilancia sobre esta norma. Lo que se ve viene solo de su título.",
  },
};

// El eje referencial merece nombre propio en la interfaz. Una norma que pasa por él lo hace
// porque **modifica una norma vigilada**, aunque su texto no mencione al colectivo: es
// justamente el retroceso silencioso que el léxico no ve. Enseñar solo los términos dejaría
// esas normas con la insignia vacía y pareciendo un falso positivo.
const EJES: Record<EjePrefiltro, string> = {
  lexico: "léxico",
  referencial: "referencial",
};

interface PrefiltroBadgeProps {
  estado: EstadoPrefiltro;
  /** Términos que la hicieron pasar; se muestran para que la decisión sea auditable. */
  terminos?: string[] | null;
  /** Qué ejes dispararon (7.3). Sin esto, una norma que pasa solo por el eje referencial
   *  aparecería sin ningún término y parecería un fallo. */
  ejes?: EjePrefiltro[] | null;
}

export function PrefiltroBadge({ estado, terminos, ejes }: PrefiltroBadgeProps) {
  const meta = META[estado];
  const coincidencias = terminos ?? [];
  const disparados = ejes ?? [];

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span
        title={meta.pista}
        className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${meta.clases}`}
      >
        <span aria-hidden="true">{meta.glifo}</span>
        {meta.etiqueta}
      </span>
      {disparados.map((eje) => (
        <span
          key={eje}
          title={
            eje === "referencial"
              ? "Modifica una norma de la lista vigilada, diga lo que diga su texto"
              : "Su texto contiene vocabulario del proyecto"
          }
          className="rounded border border-line-2 px-1 py-0.5 font-mono text-[10.5px] text-ink-3"
        >
          eje {EJES[eje]}
        </span>
      ))}
      {coincidencias.map((termino) => (
        // El término exacto, no un recuento: "pasó por 2 términos" no es auditable,
        // "pasó por «lgtbi» y «personas trans»" sí.
        <code
          key={termino}
          className="rounded bg-inset px-1 py-0.5 font-mono text-[10.5px] text-ink-2"
        >
          {termino}
        </code>
      ))}
    </span>
  );
}
