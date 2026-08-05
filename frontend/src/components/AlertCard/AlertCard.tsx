import type { AlertaFeedItem } from "../../api/mocks";
import { CLASIFICACION_ALERTA_META, COLOR_CLASSES } from "../../lib/classification";
import { ClassificationBadge } from "../ClassificationBadge/ClassificationBadge";

interface AlertCardProps {
  alerta: AlertaFeedItem;
  onVerFicha?: (id: string) => void;
}

/** Tarjeta de una alerta en el feed de Alertas. */
export function AlertCard({ alerta, onVerFicha }: AlertCardProps) {
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
        <button
          type="button"
          onClick={() => onVerFicha?.(alerta.id)}
          className="ml-auto font-sans text-sm text-link hover:text-ink"
        >
          Ver diff y fuente →
        </button>
      </div>
    </article>
  );
}
