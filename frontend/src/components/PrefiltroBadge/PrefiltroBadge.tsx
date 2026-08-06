import type { EstadoPrefiltro } from "../../api/client";

/**
 * Estado del prefiltro léxico de una norma (ADR 0007).
 *
 * Color + glifo + texto, nunca solo color, igual que `ClassificationBadge`. Y ojo con no
 * confundirlo con aquél: esto **no es una clasificación**. Decir que una norma es "relevante"
 * aquí solo significa que su título contiene vocabulario del proyecto y que por eso se
 * mirará; no dice absolutamente nada sobre si avanza o retrocede en derechos. Por eso usa
 * gris neutro y no la paleta de avance/retroceso.
 */
const META: Record<EstadoPrefiltro, { etiqueta: string; glifo: string; clases: string }> = {
  relevante: {
    etiqueta: "Pasa el prefiltro",
    glifo: "◉",
    clases: "border-ink-3 bg-surface-2 text-ink",
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
};

interface PrefiltroBadgeProps {
  estado: EstadoPrefiltro;
  /** Términos que la hicieron pasar; se muestran para que la decisión sea auditable. */
  terminos?: string[] | null;
}

export function PrefiltroBadge({ estado, terminos }: PrefiltroBadgeProps) {
  const meta = META[estado];
  const coincidencias = terminos ?? [];

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10.5px] uppercase tracking-wide ${meta.clases}`}
      >
        <span aria-hidden="true">{meta.glifo}</span>
        {meta.etiqueta}
      </span>
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
