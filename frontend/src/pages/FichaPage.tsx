import type { ReactNode } from "react";
import { fichaDetail } from "../api/mocks";
import { ArticleHistory } from "../components/ArticleHistory/ArticleHistory";
import { ClassificationBadge } from "../components/ClassificationBadge/ClassificationBadge";
import { DiffBlock } from "../components/DiffBlock/DiffBlock";
import { IntegrityPanel } from "../components/IntegrityPanel/IntegrityPanel";
import { CLASIFICACION_ALERTA_META } from "../lib/classification";

interface FichaPageProps {
  onGoTimeline: () => void;
}

interface MetaRowProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
  last?: boolean;
}

function MetaRow({ label, value, mono = false, last = false }: MetaRowProps) {
  return (
    <div
      className={`grid grid-cols-[200px_minmax(0,1fr)] gap-4 py-2.5 ${last ? "" : "border-b border-line"}`}
    >
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className={`m-0 text-sm text-ink ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

/**
 * Ficha de una norma: diff antes/después, metadatos y cadena de verificación.
 * Usa la única FichaDetail del mock (fichaDetail); cuando se cablee la API real
 * cada alerta del feed resolverá a su propia ficha por id.
 */
export function FichaPage({ onGoTimeline }: FichaPageProps) {
  const ficha = fichaDetail;
  const meta = CLASIFICACION_ALERTA_META[ficha.clasificacion];

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-6">
      <nav aria-label="Ruta de navegación" className="flex items-center gap-2 font-mono text-xs text-ink-3">
        <button type="button" onClick={onGoTimeline} className="font-mono text-xs text-link hover:text-ink">
          Alertas
        </button>
        <span>/</span>
        <span>{ficha.comunidad}</span>
        <span>/</span>
        <span>{ficha.ref}</span>
      </nav>

      <div className="mt-3.5 grid grid-cols-1 items-start gap-7 lg:grid-cols-[minmax(0,1fr)_372px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <ClassificationBadge meta={meta} />
            <span className="inline-flex items-center gap-1.5 rounded border border-line-2 bg-surface-2 px-2.5 py-1 text-xs font-medium text-ink-2">
              Ámbito {ficha.ambito.toLowerCase()}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded border border-line-2 bg-surface-2 px-2.5 py-1 text-xs font-medium text-ink-2">
              {ficha.comunidad}
            </span>
          </div>

          <h1 className="mt-3 max-w-[34ch] font-serif text-[29px] font-bold leading-tight tracking-tight text-ink">
            {ficha.titulo}
          </h1>
          <p className="mt-3 max-w-[70ch] text-sm text-ink-2">{ficha.resumen}</p>

          <DiffBlock diff={ficha.diff} />

          <div className="mt-3.5 rounded border border-line border-l-4 border-l-line-2 bg-surface p-4">
            <p className="m-0 text-sm text-ink-2">
              <strong className="font-semibold text-ink">Centinela no interpreta la norma.</strong> Mostramos
              el texto tal como aparece publicado y el enlace a la fuente oficial. La clasificación
              indica el sentido del cambio respecto al texto anterior, no una valoración política.
            </p>
          </div>

          <section className="mt-6 rounded border border-line bg-surface">
            <h2 className="border-b border-line bg-inset px-4 py-3 text-sm font-semibold text-ink">
              Metadatos de la norma
            </h2>
            <dl className="m-0 px-4 pb-3.5 pt-1">
              <MetaRow label="Título oficial" value={ficha.metadatos.tituloOficial} />
              <MetaRow label="Órgano emisor" value={ficha.metadatos.organoEmisor} />
              <MetaRow
                label="Rango"
                value={
                  <>
                    {ficha.metadatos.rango}{" "}
                    <span className="text-xs text-ink-3">({ficha.metadatos.rangoDetalle})</span>
                  </>
                }
              />
              <MetaRow label="Publicación" value={ficha.metadatos.publicacion} mono />
              <MetaRow label="Entrada en vigor" value={ficha.metadatos.entradaVigor} mono />
              <MetaRow
                label="Fuente oficial"
                last
                value={
                  <>
                    <a href="#fuente">{ficha.metadatos.fuenteLabel}</a>{" "}
                    <span className="text-xs text-ink-3">· {ficha.metadatos.fuenteNota}</span>
                  </>
                }
              />
            </dl>
          </section>
        </div>

        <aside className="sticky top-[150px] flex flex-col gap-3.5">
          <IntegrityPanel integridad={ficha.integridad} />
          <ArticleHistory articulo={ficha.diff.articulo} historial={ficha.historial} />
        </aside>
      </div>
    </main>
  );
}
