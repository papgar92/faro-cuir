import { useMemo, useState } from "react";
import { FEED } from "../api/mocks";
import { AlertCard } from "../components/AlertCard/AlertCard";
import { AlertFilters } from "../components/AlertFilters/AlertFilters";
import { DemoDataNotice } from "../components/DemoDataNotice/DemoDataNotice";

interface AlertasPageProps {
  comunidadInicial?: string;
  onGoArchivo: () => void;
}

/**
 * Feed de alertas. **Sigue sobre datos inventados**: una alerta es una detección aprobada en
 * el gate humano (`alerta` sobre `deteccion`), y ninguna de las dos tablas tiene filas hasta
 * que exista el pipeline.
 *
 * Por eso las tarjetas ya no llevan a la Ficha: la Ficha lee de la API y desde una alerta
 * ficticia no hay ninguna norma real a la que resolver. Llevan al Archivo, que es donde está
 * lo que sí existe.
 */
export function AlertasPage({ comunidadInicial, onGoArchivo }: AlertasPageProps) {
  const [comunidad, setComunidad] = useState(comunidadInicial ?? "todas");
  const [ambito, setAmbito] = useState("todos");
  const [tipo, setTipo] = useState("todos");

  const comunidades = useMemo(() => Array.from(new Set(FEED.map((item) => item.com))), []);
  const ambitos = useMemo(() => Array.from(new Set(FEED.map((item) => item.ambito))), []);

  const feed = useMemo(
    () =>
      FEED.filter(
        (item) =>
          (comunidad === "todas" || item.com === comunidad) &&
          (ambito === "todos" || item.ambito === ambito) &&
          (tipo === "todos" || item.tipo === tipo),
      ),
    [comunidad, ambito, tipo],
  );

  const clearFilters = () => {
    setComunidad("todas");
    setAmbito("todos");
    setTipo("todos");
  };

  const countLabel = `${feed.length} ${feed.length === 1 ? "alerta" : "alertas"} · de 1.284 documentos analizados hoy`;

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <div className="max-w-[900px]">
        <DemoDataNotice
          que="El feed de alertas"
          depende="las detecciones aprobadas en el gate humano (deteccion, alerta)"
          onIrAlArchivo={onGoArchivo}
        />
        <h1 className="font-serif text-2xl font-bold tracking-tight text-ink">Alertas validadas</h1>
        <p className="mt-2 max-w-[66ch] text-sm text-ink-2">
          Detecciones revisadas por una persona antes de publicarse. Orden cronológico inverso. Cada
          titular describe qué cambia en el texto, sin valoración.
        </p>
      </div>

      <AlertFilters
        comunidades={comunidades}
        ambitos={ambitos}
        comunidad={comunidad}
        ambito={ambito}
        tipo={tipo}
        onComunidadChange={setComunidad}
        onAmbitoChange={setAmbito}
        onTipoChange={setTipo}
        onClear={clearFilters}
      />

      <div className="mb-3 mt-5 font-mono text-xs text-ink-3">{countLabel}</div>

      <div className="max-w-[900px]">
        {feed.map((alerta) => (
          <AlertCard key={alerta.id} alerta={alerta} onGoArchivo={onGoArchivo} />
        ))}
      </div>

      {feed.length === 0 && (
        <div className="max-w-[900px] rounded border border-dashed border-line-2 bg-surface p-8 text-center">
          <p className="m-0 text-base font-semibold text-ink">Ninguna alerta coincide con estos filtros</p>
          <p className="mt-1.5 text-sm text-ink-2">Prueba a ampliar el ámbito o el rango de comunidades.</p>
          <button
            type="button"
            onClick={clearFilters}
            className="mt-3.5 rounded bg-ink px-3.5 py-2 text-sm text-surface"
          >
            Limpiar filtros
          </button>
        </div>
      )}
    </main>
  );
}
