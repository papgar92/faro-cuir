import { useState } from "react";
import { obtenerCobertura } from "../api/client";
import { REGIONS } from "../api/mocks";
import { useRecurso } from "../api/useRecurso";
import { ClassificationBadge } from "../components/ClassificationBadge/ClassificationBadge";
import { DemoDataNotice } from "../components/DemoDataNotice/DemoDataNotice";
import { CCAA_PATHS } from "../components/MapaCCAA/ccaa-paths";
import { MapaCCAA } from "../components/MapaCCAA/MapaCCAA";
import { Manifiesto } from "../components/Manifiesto/Manifiesto";
import { RegionDetailPanel } from "../components/RegionDetailPanel/RegionDetailPanel";
import { TopAlertsRanking } from "../components/TopAlertsRanking/TopAlertsRanking";
import { ESTADO_MAPA_META, type EstadoMapa } from "../lib/classification";

const ESTADOS_LEYENDA = Object.keys(ESTADO_MAPA_META) as EstadoMapa[];

interface MapaPageProps {
  onGoArchivo: () => void;
  onGoTimeline: (comunidad?: string) => void;
}

/**
 * Mapa por comunidad autónoma. **Sigue sobre datos inventados**: el color de cada comunidad
 * se deriva de sus detecciones validadas (`deteccion`), y esa tabla está vacía hasta que
 * exista el pipeline. Un mapa es justo el formato que más se lee como dato duro, así que el
 * aviso va arriba y no en una nota al pie.
 */
export function MapaPage({ onGoArchivo, onGoTimeline }: MapaPageProps) {
  const [hover, setHover] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const activeCode = hover ?? pinned;
  const activeRegion = activeCode ? REGIONS[activeCode] : null;
  // Territorio dibujado en el mapa del que no hay ninguna fila. Hoy son Ceuta y
  // Melilla. Sin esta rama, pulsarlas no hacía absolutamente nada y quedaba como
  // un fallo de la interfaz en vez de como lo que es: un hueco de cobertura.
  const activeSinFuente =
    activeCode && !activeRegion ? CCAA_PATHS.find((p) => p.code === activeCode) : undefined;

  // Cobertura real de fuentes (ADR 0014). Una sola petición para todas las comunidades y no
  // una por selección: son 61 filas agregadas en la base, así que traerlo entero cuesta menos
  // que ir pidiéndolo cada vez que el ratón pasa por encima de una comunidad.
  const coberturaEstado = useRecurso((signal) => obtenerCobertura(signal), []);
  const coberturaPorCodigo =
    coberturaEstado.fase === "listo"
      ? new Map(coberturaEstado.datos.por_ccaa.map((c) => [c.ccaa_codigo, c]))
      : undefined;

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <Manifiesto />

      <DemoDataNotice
        que="El estado de cada comunidad"
        depende="las detecciones validadas por comunidad (deteccion)"
        onIrAlArchivo={onGoArchivo}
      />

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
            <span className="flex items-center gap-1.5 text-xs text-ink-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3 rounded-[2px] border border-line-2"
                style={{
                  // Misma trama que el patrón SVG del mapa, con los mismos tokens.
                  backgroundImage:
                    "repeating-linear-gradient(45deg, var(--color-line-2) 0 1.4px, var(--color-surface-2) 1.4px 5px)",
                }}
              />
              Sin fuente vigilada
            </span>
            <span className="ml-auto font-mono text-xs text-ink-3">color + símbolo + texto</span>
          </div>

          <MapaCCAA
            regions={REGIONS}
            activeCode={activeCode}
            onEnter={setHover}
            onLeave={() => setHover(null)}
            onPick={(code) => setPinned((prev) => (prev === code ? null : code))}
          />

          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-0.5 pb-3.5 pt-1.5 font-mono text-xs text-ink-3">
            <span>
              Comunidad seleccionada: {activeRegion?.name ?? activeSinFuente?.name ?? "ninguna"}
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
            <TopAlertsRanking regions={REGIONS} />
          )}
        </aside>
      </div>
    </main>
  );
}
