import { useState } from "react";
import { REGIONS } from "../api/mocks";
import { ClassificationBadge } from "../components/ClassificationBadge/ClassificationBadge";
import { MapaCCAA } from "../components/MapaCCAA/MapaCCAA";
import { RegionDetailPanel } from "../components/RegionDetailPanel/RegionDetailPanel";
import { TopAlertsRanking } from "../components/TopAlertsRanking/TopAlertsRanking";
import { ESTADO_MAPA_META, type EstadoMapa } from "../lib/classification";

const ESTADOS_LEYENDA = Object.keys(ESTADO_MAPA_META) as EstadoMapa[];

interface MapaPageProps {
  onGoFicha: () => void;
  onGoTimeline: (comunidad?: string) => void;
}

export function MapaPage({ onGoFicha, onGoTimeline }: MapaPageProps) {
  const [hover, setHover] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const activeCode = hover ?? pinned;
  const activeRegion = activeCode ? REGIONS[activeCode] : null;

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <div className="grid grid-cols-1 items-start gap-7 lg:grid-cols-[minmax(0,1fr)_372px]">
        <section className="rounded border border-line bg-surface px-5 pb-2 pt-5">
          <div className="flex flex-wrap items-baseline justify-between gap-4">
            <h1 className="font-serif text-2xl font-bold tracking-tight text-ink">
              Estado de los derechos por comunidad autónoma
            </h1>
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
            <span className="ml-auto font-mono text-xs text-ink-3">color + símbolo + texto</span>
          </div>

          <MapaCCAA
            regions={REGIONS}
            activeCode={activeCode}
            onEnter={setHover}
            onLeave={() => setHover(null)}
            onPick={(code) => setPinned((prev) => (prev === code ? null : code))}
          />

          <div className="flex items-center justify-between px-0.5 pb-3.5 pt-1.5 font-mono text-xs text-ink-3">
            <span>Comunidad seleccionada: {activeRegion?.name ?? "ninguna"}</span>
            <span>Geometría: IGN · CC BY 4.0</span>
          </div>
        </section>

        <aside className="sticky top-[150px] rounded border border-line bg-surface">
          {activeRegion ? (
            <RegionDetailPanel
              region={activeRegion}
              onGoFicha={onGoFicha}
              onGoTimeline={() => onGoTimeline(activeRegion.name)}
            />
          ) : (
            <TopAlertsRanking regions={REGIONS} />
          )}
        </aside>
      </div>
    </main>
  );
}
