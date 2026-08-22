import { useEffect, useState } from "react";
import { listarAlertas, obtenerCobertura } from "../api/client";
import { useRecurso } from "../api/useRecurso";
import { ClassificationBadge } from "../components/ClassificationBadge/ClassificationBadge";
import { CCAA_PATHS } from "../components/MapaCCAA/ccaa-paths";
import { MapaCCAA } from "../components/MapaCCAA/MapaCCAA";
import { Manifiesto } from "../components/Manifiesto/Manifiesto";
import { RegionDetailPanel } from "../components/RegionDetailPanel/RegionDetailPanel";
import { TopAlertsRanking } from "../components/TopAlertsRanking/TopAlertsRanking";
import { ESTADO_MAPA_META, type EstadoMapa } from "../lib/classification";
import { CoberturaTotal } from "../components/CoberturaTotal/CoberturaTotal";
import { PanelEstatal } from "../components/PanelEstatal/PanelEstatal";
import { construirRegiones, resumenEstatal } from "../lib/mapa";
import { escribirUrl } from "../lib/navigation";

const ESTADOS_LEYENDA = Object.keys(ESTADO_MAPA_META) as EstadoMapa[];

interface MapaPageProps {
  onGoArchivo: () => void;
  onGoTimeline: (comunidad?: string) => void;
  /** Comunidad que venía en la URL (`?ccaa=CT`). Se usa como selección inicial. */
  ccaaInicial?: string;
}

/**
 * Mapa por comunidad autónoma, **con datos reales desde el 2026-08-17**.
 *
 * El color sale de las alertas **aprobadas por una persona** (`GET /api/alertas`) y el
 * territorio de la watchlist, no de la fuente: una ley autonómica se publica en el BOE, así que
 * por fuente sería «estatal» y la comunidad quedaría en blanco justo en el caso que el proyecto
 * existe para enseñar.
 *
 * **Lo que este mapa no puede hacer, y es lo que más condiciona su diseño**: pintar de color
 * neutro una comunidad sin alertas. Un mapa es el formato que más se lee como dato duro, y un
 * gris «estable» sobre una comunidad donde nadie está mirando convierte el silencio en
 * tranquilidad. Por eso hay tres categorías y dos de ellas no son un color, sino trama: una para
 * «vigilada, sin alertas aprobadas» y otra para «sin fuente vigilada». Ver `lib/mapa.ts`.
 */
export function MapaPage({ onGoArchivo, onGoTimeline, ccaaInicial }: MapaPageProps) {
  const [hover, setHover] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(ccaaInicial ?? null);
  const activeCode = hover ?? pinned;

  // La comunidad FIJADA va a la URL; la del ratón no. Es la distinción que hace que el enlace
  // sirva para algo: `?ccaa=CT` significa «alguien eligió Catalunya», no «el cursor pasó por
  // encima». Escribir el hover llenaría la barra de direcciones de ruido y, con `replaceState`,
  // dejaría la última comunidad rozada como si fuera la elegida.
  useEffect(() => {
    escribirUrl({ screen: "mapa", ccaa: pinned ?? undefined });
  }, [pinned]);
  // Las dos peticiones que sostienen el mapa. Van juntas y a la vez: la cobertura dice dónde se
  // mira y las alertas qué ha salido, y ninguna de las dos por sí sola permite pintar sin mentir.
  const coberturaEstado = useRecurso((signal) => obtenerCobertura(signal), []);
  // 100 es el tope duro de la API (`LIMITE_MAXIMO`), no un número elegido aquí: pedir más
  // devuelve 422 y el mapa se quedaba diciendo «no hay ninguna alerta aprobada» mientras el
  // sistema tenía una. Ese fallo —afirmar ausencia cuando lo que hay es un error— es justo el
  // que este proyecto no puede permitirse, así que el pie enseña el estado de la petición.
  const alertasEstado = useRecurso((signal) => listarAlertas({ limite: 100 }, signal), []);
  const regiones = construirRegiones(
    alertasEstado.fase === "listo" ? alertasEstado.datos : undefined,
    coberturaEstado.fase === "listo" ? coberturaEstado.datos : undefined,
  );
  const activeRegion = activeCode ? (regiones[activeCode] ?? null) : null;
  const estatal = resumenEstatal(alertasEstado.fase === "listo" ? alertasEstado.datos : []);
  // Territorio dibujado en el mapa del que no hay ninguna fila. Hoy son Ceuta y
  // Melilla. Sin esta rama, pulsarlas no hacía absolutamente nada y quedaba como
  // un fallo de la interfaz en vez de como lo que es: un hueco de cobertura.
  const activeSinFuente =
    activeCode && !activeRegion ? CCAA_PATHS.find((p) => p.code === activeCode) : undefined;

  const coberturaPorCodigo =
    coberturaEstado.fase === "listo"
      ? new Map(coberturaEstado.datos.por_ccaa.map((c) => [c.ccaa_codigo, c]))
      : undefined;

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <Manifiesto />

      <div className="grid grid-cols-1 items-start gap-7 lg:grid-cols-[minmax(0,1fr)_372px]">
        <section className="rounded border border-line bg-surface px-5 pb-2 pt-5">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            {/* h2 y no h1: el h1 de la página es el titular del manifiesto, que va
                antes. Dos h1 en la misma pantalla rompen el orden para un lector. */}
            <h2 className="font-serif text-2xl font-bold tracking-tight text-ink">
              Estado de los derechos por comunidad autónoma
            </h2>
            <span className="text-xs text-ink-3">Ventana de evaluación: últimos 90 días</span>
          </div>
          <p className="mt-2 max-w-[64ch] text-sm text-ink-2">
            Clasificación derivada de los cambios normativos detectados y validados. Pasa el cursor o
            pulsa una comunidad para ver su resumen. Cada comunidad enlaza a sus alertas y a la fuente
            oficial.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-4 rounded border border-line bg-inset p-3">
            {ESTADOS_LEYENDA.map((estado) => (
              <ClassificationBadge key={estado} meta={ESTADO_MAPA_META[estado]} />
            ))}
            {/* Ceuta y Melilla se dibujan pero no tienen fuente en docs/fuentes.md.
                Un gris igual al de "estable" diría que se han mirado y están bien. */}
            {/* La trama densa dejó de ser una sola: ahora tiene tres pasos por deuda de
                cobertura, y la leyenda tiene que enseñar los tres o el degradado del mapa no se
                puede leer. El orden va de menos a más, como se lee. */}
            <span className="flex items-center gap-1.5 text-xs text-ink-2">
              <span className="flex gap-0.5" aria-hidden="true">
                {[
                  { sep: "7px", grosor: "1px" },
                  { sep: "5px", grosor: "1.4px" },
                  { sep: "3.4px", grosor: "1.6px" },
                ].map((paso) => (
                  <span
                    key={paso.sep}
                    className="inline-block h-3 w-3 rounded-[2px] border border-line-2"
                    style={{
                      backgroundImage: `repeating-linear-gradient(45deg, var(--color-line-2) 0 ${paso.grosor}, var(--color-surface-2) ${paso.grosor} ${paso.sep})`,
                    }}
                  />
                ))}
              </span>
              Sin vigilar — 1-2 · 3-5 · 6+ boletines pendientes
            </span>
            {/* La categoría que evita la mentira más fácil de este mapa: aquí SÍ se mira y no
                ha salido nada aprobado. No es «estable». */}
            <span className="flex items-center gap-1.5 text-xs text-ink-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 rounded-[2px] border border-line-2"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, var(--color-line-2) 0 1px, var(--color-surface) 1px 9px)",
                }}
              />
              Vigilada, sin alertas
            </span>
            <span className="ml-auto font-mono text-xs text-ink-3">color + símbolo + texto</span>
          </div>

          <PanelEstatal resumen={estatal} onVerAlertas={() => onGoTimeline()} />

          <MapaCCAA
            regions={regiones}
            activeCode={activeCode}
            onEnter={setHover}
            onLeave={() => setHover(null)}
            onPick={(code) => setPinned((prev) => (prev === code ? null : code))}
          />

          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-0.5 pb-3.5 pt-1.5 font-mono text-xs text-ink-3">
            <span>
              Comunidad seleccionada: {activeRegion?.name ?? activeSinFuente?.name ?? "ninguna"}
            </span>
            <span>
              {alertasEstado.fase === "listo"
                ? `${alertasEstado.datos.length} alerta${alertasEstado.datos.length === 1 ? "" : "s"} aprobada${alertasEstado.datos.length === 1 ? "" : "s"} en total`
                : alertasEstado.fase === "error"
                  ? "no se han podido cargar las alertas"
                  : "cargando alertas…"}
            </span>
            <span>Geometría: IGN · CC BY 4.0 · proyección cónica equivalente</span>
          </div>
        </section>

        <aside className="sticky top-[150px] rounded border border-line bg-surface">
          {activeRegion ? (
            <RegionDetailPanel
              region={activeRegion}
              cobertura={coberturaPorCodigo?.get(activeRegion.code)}
              onGoArchivo={onGoArchivo}
              onGoTimeline={() => onGoTimeline(activeRegion.name)}
            />
          ) : activeSinFuente ? (
            <div className="p-5">
              <h3 className="font-serif text-lg font-bold text-ink">{activeSinFuente.name}</h3>
              <p className="mt-0.5 text-xs uppercase tracking-wide text-ink-3">Ciudad autónoma</p>
              <p className="mt-3 text-sm leading-relaxed text-ink-2">
                Faro Cuir todavía <strong className="font-semibold text-ink">no vigila</strong> el
                boletín oficial de {activeSinFuente.name}. Aparece en el mapa porque el mapa tiene
                que estar completo, y con trama porque aquí no hay nada medido: no significa que no
                pase nada, significa que nadie está mirando.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-ink-2">
                Las fuentes confirmadas y las que quedan por auditar están en{" "}
                <code className="font-mono text-[13px] text-ink">docs/fuentes.md</code>.
              </p>
            </div>
          ) : (
            // En reposo el `aside` enseñaba solo un ranking de 3 filas, que con 3 comunidades no
            // ordena nada. Debajo va el dato que de verdad explica la pantalla: 2 fuentes de 45.
            <>
              <TopAlertsRanking regions={regiones} />
              <CoberturaTotal
                cobertura={coberturaEstado.fase === "listo" ? coberturaEstado.datos : undefined}
                onGoArchivo={onGoArchivo}
              />
            </>
          )}
        </aside>
      </div>
    </main>
  );
}
