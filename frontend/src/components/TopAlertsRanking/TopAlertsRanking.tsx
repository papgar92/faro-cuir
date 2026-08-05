import type { RegionSummary } from "../../api/mocks";
import { COLOR_CLASSES, ESTADO_MAPA_META } from "../../lib/classification";

interface TopAlertsRankingProps {
  regions: Record<string, RegionSummary>;
  limit?: number;
}

/** Ranking de comunidades por alertas activas, mostrado cuando no hay ninguna seleccionada. */
export function TopAlertsRanking({ regions, limit = 6 }: TopAlertsRankingProps) {
  const values = Object.values(regions);
  const ranked = values
    .filter((region) => region.alerts > 0)
    .sort((a, b) => b.alerts - a.alerts)
    .slice(0, limit);
  const sinCambios = values.filter((region) => region.alerts === 0).length;

  return (
    <div className="p-5">
      <h2 className="font-serif text-lg font-bold text-ink">Vista general</h2>
      <p className="mt-1.5 text-sm text-ink-2">
        Ninguna comunidad seleccionada. Comunidades con más alertas activas ahora:
      </p>
      <ul className="mt-3.5 flex list-none flex-col border-t border-line p-0">
        {ranked.map((region) => {
          const meta = ESTADO_MAPA_META[region.state];
          const colors = COLOR_CLASSES[meta.color];
          return (
            <li key={region.code} className="flex items-center gap-2.5 border-b border-line py-2.5">
              <span
                aria-hidden="true"
                className={`grid h-[18px] w-[18px] flex-shrink-0 place-items-center rounded-sm text-[10px] font-bold ${colors.bg} ${colors.text}`}
              >
                {meta.glyph}
              </span>
              <span className="text-sm text-ink">{region.name}</span>
              <span className={`ml-auto font-mono text-sm font-medium ${colors.text}`}>{region.alerts}</span>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 rounded border border-line bg-inset p-3.5">
        <p className="m-0 text-xs text-ink-2">
          {sinCambios} comunidades no registran ningún cambio en la ventana actual. Eso no siempre es
          buena noticia: puede indicar bloqueo de tramitación.
        </p>
      </div>
    </div>
  );
}
