import type { CoberturaCcaaApi } from "../../api/client";
import type { RegionMapa } from "../../lib/mapa";
import { COLOR_CLASSES, ESTADO_MAPA_META } from "../../lib/classification";
import { ClassificationBadge } from "../ClassificationBadge/ClassificationBadge";
import { CoberturaCcaa } from "../CoberturaCcaa/CoberturaCcaa";

interface RegionDetailPanelProps {
  region: RegionMapa;
  /**
   * Cobertura real de fuentes de esta comunidad (ADR 0014). `undefined` mientras la petición
   * está en vuelo o si la API no responde: en ese caso no se pinta el bloque, en vez de
   * pintar ceros. Un cero inventado aquí diría "no vigilamos nada", que es una afirmación
   * distinta de "todavía no lo sé".
   */
  cobertura?: CoberturaCcaaApi;
  onGoArchivo: () => void;
  onGoTimeline: () => void;
}

/** Resumen de la comunidad activa (hover o pin) en el sidebar del mapa. */
export function RegionDetailPanel({
  region,
  cobertura,
  onGoArchivo,
  onGoTimeline,
}: RegionDetailPanelProps) {
  // `null` = ninguna alerta aprobada todavía. **No se sustituye por «estable»**: el panel dice
  // que no hay conclusión, que es lo que hay.
  const meta = region.state ? ESTADO_MAPA_META[region.state] : null;
  // Sin conclusión se usa el color neutro **solo para el número**, nunca para una insignia de
  // estado: pintar una insignia gris con la palabra «estable» es la mentira que este panel
  // existe para no contar.
  const colors = COLOR_CLASSES[meta?.color ?? "neu"];
  const hasChange = Boolean(region.title);

  return (
    <div className="p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-serif text-xl font-bold text-ink">{region.name}</h2>
        <span className="font-mono text-xs text-ink-3">{region.code}</span>
      </div>

      <div className="mt-3">
        {meta ? (
          <ClassificationBadge meta={meta} />
        ) : (
          <p className="text-sm leading-relaxed text-ink-2">
            {region.vigilada ? (
              <>
                <strong className="font-semibold text-ink">Sin alertas aprobadas todavía.</strong>{" "}
                Se vigilan {region.fuentesVigiladas} de {region.fuentesConocidas} fuentes de esta
                comunidad. Que no haya alertas no significa que no haya cambios: significa que
                ninguno ha llegado al final del pipeline y ha pasado la revisión humana.
              </>
            ) : (
              <>
                <strong className="font-semibold text-ink">Aquí no estamos mirando.</strong> De las{" "}
                {region.fuentesConocidas} fuentes conocidas de esta comunidad no hay ninguna
                integrada todavía, así que el silencio de este mapa sobre ella no dice nada.
              </>
            )}
          </p>
        )}
      </div>

      <dl className="mt-4 border-t border-line">
        <div className="flex items-baseline justify-between gap-3 border-b border-line py-2.5">
          <dt className="text-xs text-ink-2">Alertas activas</dt>
          <dd className={`m-0 font-mono text-lg font-medium ${region.alerts === 0 ? "text-ink-3" : colors.text}`}>
            {region.alerts}
          </dd>
        </div>
      </dl>

      {/* Cobertura real, medida contra la tabla `fuente`. Va justo debajo de las cifras
          inventadas y encima del "último cambio" a propósito: es lo único de este panel que
          no es una maqueta, y da la escala de lo que el resto todavía no puede afirmar. */}
      <CoberturaCcaa cobertura={cobertura} />

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
              <span>{region.rango}</span>
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
