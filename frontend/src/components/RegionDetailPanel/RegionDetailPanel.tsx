import type { RegionSummary } from "../../api/mocks";
import { COLOR_CLASSES, ESTADO_MAPA_META } from "../../lib/classification";
import { ClassificationBadge } from "../ClassificationBadge/ClassificationBadge";

interface RegionDetailPanelProps {
  region: RegionSummary;
  onGoArchivo: () => void;
  onGoTimeline: () => void;
}

/** Resumen de la comunidad activa (hover o pin) en el sidebar del mapa. */
export function RegionDetailPanel({ region, onGoArchivo, onGoTimeline }: RegionDetailPanelProps) {
  const meta = ESTADO_MAPA_META[region.state];
  const colors = COLOR_CLASSES[meta.color];
  const hasChange = Boolean(region.title);

  return (
    <div className="p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-serif text-xl font-bold text-ink">{region.name}</h2>
        <span className="font-mono text-xs text-ink-3">{region.code}</span>
      </div>

      <div className="mt-3">
        <ClassificationBadge meta={meta} />
      </div>

      <dl className="mt-4 border-t border-line">
        <div className="flex items-baseline justify-between gap-3 border-b border-line py-2.5">
          <dt className="text-xs text-ink-2">Alertas activas</dt>
          <dd className={`m-0 font-mono text-lg font-medium ${region.alerts === 0 ? "text-ink-3" : colors.text}`}>
            {region.alerts}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3 border-b border-line py-2.5">
          <dt className="text-xs text-ink-2">Documentos vigilados</dt>
          <dd className="m-0 font-mono text-sm text-ink">{region.sources}</dd>
        </div>
      </dl>

      <div className="mt-4">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
          Último cambio detectado
        </div>

        {hasChange ? (
          <>
            <p className="mt-2 text-sm leading-snug text-ink">{region.title}</p>
            <div className="mt-2 flex flex-wrap gap-3.5 font-mono text-xs text-ink-3">
              <span>{region.date}</span>
              <span>{region.rango}</span>
              <span>{region.ambito}</span>
            </div>
            <div className="mt-3 flex gap-2">
              {/* Esta comunidad y su cambio son inventados: no hay ficha real detrás, así
                  que el botón lleva al Archivo y lo dice. */}
              <button
                type="button"
                onClick={onGoArchivo}
                className="rounded bg-ink px-3.5 py-2 text-sm font-medium text-surface hover:opacity-85"
              >
                Ver el archivo real
              </button>
              <button
                type="button"
                onClick={onGoTimeline}
                className="rounded border border-line-2 px-3.5 py-2 text-sm text-ink hover:border-ink-3"
              >
                Alertas de la comunidad
              </button>
            </div>
          </>
        ) : (
          <div className="mt-2.5 rounded border border-dashed border-line-2 bg-inset p-4">
            <p className="m-0 text-sm text-ink-2">
              Sin cambios detectados en los últimos 90 días. El seguimiento sigue activo: se revisan a
              diario el boletín oficial y la actividad parlamentaria.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
