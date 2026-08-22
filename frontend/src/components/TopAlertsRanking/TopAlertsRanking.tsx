import type { RegionMapa } from "../../lib/mapa";
import { COLOR_CLASSES, ESTADO_MAPA_META } from "../../lib/classification";

interface TopAlertsRankingProps {
  regions: Record<string, RegionMapa>;
  limit?: number;
}

/** Ranking de comunidades por alertas activas, mostrado cuando no hay ninguna seleccionada. */
export function TopAlertsRanking({ regions, limit = 6 }: TopAlertsRankingProps) {
  const values = Object.values(regions);
  const ranked = values
    .filter((region) => region.alerts > 0)
    .sort((a, b) => b.alerts - a.alerts)
    .slice(0, limit);
  // **Dos silencios distintos, contados por separado** (2026-08-17, con datos reales). Antes
  // esto era un solo número con el rótulo «no registran ningún cambio», que sobre datos de
  // verdad sería falso: mezclaba las comunidades donde se mira y no ha salido nada con aquellas
  // donde no hay ni una fuente integrada. La segunda cifra es hoy la grande, y decirlo es la
  // mitad del valor de esta pantalla.
  const vigiladasSinAlertas = values.filter((r) => r.alerts === 0 && r.vigilada).length;
  const sinVigilar = values.filter((r) => r.alerts === 0 && !r.vigilada).length;
  // El denominador que hace legible al numerador. Ver el comentario de abajo.
  const total = values.length;

  return (
    <div className="p-5">
      <h2 className="font-serif text-lg font-bold text-ink">Vista general</h2>
      <p className="mt-1.5 text-sm text-ink-2">
        {ranked.length > 0
          ? "Ninguna comunidad seleccionada. Comunidades con alertas aprobadas:"
          : "Ninguna comunidad seleccionada. Todavía no hay ninguna alerta aprobada."}
      </p>
      <ul className="mt-3.5 flex list-none flex-col border-t border-line p-0">
        {ranked.map((region) => {
          // El ranking solo lista comunidades CON alertas, así que aquí el estado nunca es
          // nulo; el respaldo existe para que el tipo no obligue a un `!` que mañana mienta.
          const meta = ESTADO_MAPA_META[region.state ?? "alerta"];
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
        {/*
          **El denominador va escrito, y no es un detalle.** El mapa dibuja 19 territorios (17
          comunidades más Ceuta y Melilla), asi que este recuento daba «17» — el mismo número que
          la cabecera usa para «17 CCAA + BOE». Leídos juntos, parecía decir que no se vigila
          ninguna comunidad, cuando Catalunya sí lo está. Un número correcto que se lee al revés
          es un número mal publicado, y esta pantalla mide precisamente huecos de cobertura.
        */}
        <p className="m-0 text-xs text-ink-2">
          <strong className="font-semibold text-ink">{vigiladasSinAlertas}</strong> con fuente
          vigilada y sin ninguna alerta aprobada todavía, y{" "}
          <strong className="font-semibold text-ink">{sinVigilar}</strong> de los {total} territorios
          del mapa donde aún no hay ninguna fuente integrada. Lo segundo no es una medición: es un
          hueco de cobertura, y el mapa lo pinta con trama para no confundirlo con tranquilidad.
        </p>
      </div>
    </div>
  );
}
