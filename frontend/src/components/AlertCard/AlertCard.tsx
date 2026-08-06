import type { AlertaFeedItem } from "../../api/mocks";
import { CLASIFICACION_ALERTA_META, COLOR_CLASSES } from "../../lib/classification";
import { ClassificationBadge } from "../ClassificationBadge/ClassificationBadge";

interface AlertCardProps {
  alerta: AlertaFeedItem;
  onGoArchivo: () => void;
}

/** Tarjeta de una alerta en el feed de Alertas. Datos de ejemplo (ver DemoDataNotice). */
export function AlertCard({ alerta, onGoArchivo }: AlertCardProps) {
  const meta = CLASIFICACION_ALERTA_META[alerta.tipo];
  const colors = COLOR_CLASSES[meta.color];

  return (
    <article
      className={`mb-2.5 max-w-[900px] rounded border border-line ${colors.borderLeft} border-l-4 bg-surface p-4`}
    >
      <div className="flex flex-wrap items-center gap-2.5">
        <ClassificationBadge meta={meta} />
        <span className="text-sm font-semibold text-ink">{alerta.com}</span>
        <span className="text-xs text-ink-3">·</span>
        <span className="text-xs text-ink-2">{alerta.ambito}</span>
        <span className="ml-auto font-mono text-xs text-ink-3">{alerta.date}</span>
      </div>
      <h3 className="mt-2.5 text-base font-semibold leading-snug text-ink">{alerta.title}</h3>
      <div className="mt-2.5 flex flex-wrap items-center gap-3.5 font-mono text-xs text-ink-3">
        <span>{alerta.rango}</span>
        <span>{alerta.ref}</span>
        {/* Antes decía "Ver diff y fuente" y abría la Ficha. Esta alerta es inventada: no hay
            diff que ver ni norma real a la que resolver, así que el botón dice a dónde lleva
            de verdad en vez de prometer una ficha que no existe. */}
        <button
          type="button"
          onClick={onGoArchivo}
          className="ml-auto font-sans text-sm text-link hover:text-ink"
        >
          Ver el archivo real →
        </button>
      </div>
    </article>
  );
}
