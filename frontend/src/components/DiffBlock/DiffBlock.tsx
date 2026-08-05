import type { DiffSegment, FichaDetail } from "../../api/mocks";

interface DiffBlockProps {
  diff: FichaDetail["diff"];
}

function Segment({ segment }: { segment: DiffSegment }) {
  if (segment.tipo === "same") return <>{segment.text}</>;

  if (segment.tipo === "del") {
    return (
      <mark className="bg-del-bg px-0.5 text-ink line-through decoration-reg">
        {/* El tachado + color no es autodescriptivo para lectores de pantalla. */}
        <span className="sr-only">texto eliminado: </span>
        {segment.text}
      </mark>
    );
  }

  return (
    <mark className="bg-ins-bg px-0.5 font-semibold text-ink">
      <span className="sr-only">texto añadido: </span>
      {segment.text}
    </mark>
  );
}

/** Comparación antes/después de un artículo, con leyenda y estadísticas del diff. */
export function DiffBlock({ diff }: DiffBlockProps) {
  return (
    <section className="mt-6 overflow-hidden rounded border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-3.5 border-b border-line bg-inset px-4 py-3">
        <h2 className="text-sm font-semibold tracking-wide text-ink">
          Comparación del texto · {diff.articulo}
        </h2>
        <div className="flex items-center gap-3.5 font-mono text-xs text-ink-3">
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm border border-reg bg-del-bg" />
            suprimido
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm border border-adv bg-ins-bg" />
            añadido
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2">
        <div className="border-b border-line sm:border-b-0 sm:border-r">
          <div className="flex items-baseline gap-2 border-b border-line px-4 py-2.5">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
              {diff.antes.label}
            </span>
            <span className="font-mono text-xs text-ink-2">{diff.antes.fuente}</span>
          </div>
          <p className="p-4 text-sm leading-[1.72] text-ink">
            {diff.antes.segmentos.map((segmento, i) => (
              <Segment key={i} segment={segmento} />
            ))}
          </p>
        </div>
        <div>
          <div className="flex items-baseline gap-2 border-b border-line px-4 py-2.5">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
              {diff.despues.label}
            </span>
            <span className="font-mono text-xs text-ink-2">{diff.despues.fuente}</span>
          </div>
          <p className="p-4 text-sm leading-[1.72] text-ink">
            {diff.despues.segmentos.map((segmento, i) => (
              <Segment key={i} segment={segmento} />
            ))}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-5 border-t border-line bg-inset px-4 py-3 font-mono text-xs text-ink-3">
        <span>{diff.stats.fragmentosModificados} fragmentos modificados</span>
        <span>+{diff.stats.palabrasAnadidas} palabras</span>
        <span>−{diff.stats.palabrasEliminadas} palabras</span>
        <span className="ml-auto">{diff.stats.nota}</span>
      </div>
    </section>
  );
}
