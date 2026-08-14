import { useState } from "react";
import { type AlertaApi, listarAlertas } from "../api/client";
import { describirError, useRecurso } from "../api/useRecurso";
import { AlertCard } from "../components/AlertCard/AlertCard";
import { nombreTerritorio } from "../lib/territorio";

interface AlertasPageProps {
  comunidadInicial?: string;
  onGoArchivo: () => void;
}

/**
 * Feed de alertas. **Lee de la API desde el 2026-08-14**, con el gate humano ya implementado
 * (ADR 0017): cada tarjeta de aquí es una detección que una persona aprobó.
 *
 * Dos cosas que cambiaron al dejar de ser una maqueta y conviene no deshacer:
 *
 * - **Los filtros del diseño original no están.** Eran comunidad, ámbito temático y tipo, y de
 *   los tres solo uno tiene dato real hoy: `norma.ambito` sigue nulo hasta que el extractor lo
 *   rellene. Un desplegable que no filtra nada es peor que no tenerlo, porque promete una
 *   capacidad que no existe. Queda el filtro por clasificación, que sí se puede sostener.
 *   `AlertFilters` sigue en el repositorio esperando a que haya con qué; no borrarlo.
 * - **El recuento no dice "de 1.284 documentos analizados hoy".** Esa cifra era del mock. Lo
 *   que se puede decir con verdad es cuántas alertas hay, y eso es lo que dice.
 *
 * El estado vacío es importante y no es un error: significa que nada ha pasado el gate, que es
 * distinto de que no haya nada detectado. La pantalla lo dice con esas palabras.
 */

const CLASIFICACIONES: Array<{ valor: AlertaApi["clasificacion"] | "todas"; etiqueta: string }> = [
  { valor: "todas", etiqueta: "Todas" },
  { valor: "retroceso", etiqueta: "Retrocesos" },
  { valor: "avance", etiqueta: "Avances" },
  { valor: "indeterminado", etiqueta: "Sin signo" },
  { valor: "neutro", etiqueta: "Neutras" },
];

export function AlertasPage({ comunidadInicial, onGoArchivo }: AlertasPageProps) {
  const [clasificacion, setClasificacion] = useState<AlertaApi["clasificacion"] | "todas">("todas");
  const estado = useRecurso(
    (signal) =>
      listarAlertas(
        { limite: 100, ...(clasificacion === "todas" ? {} : { clasificacion }) },
        signal,
      ),
    [clasificacion],
  );

  // El mapa puede llegar con una comunidad ya elegida. Se filtra en cliente porque el
  // territorio de una alerta no es una columna: sale de la watchlist, cruzando la norma
  // vigilada que toca (ver `schemas/alerta.py`).
  const filtrar = (alertas: AlertaApi[]) =>
    comunidadInicial === undefined
      ? alertas
      : alertas.filter((a) =>
          a.normas_vigiladas.some((n) => nombreTerritorio(n.ambito) === comunidadInicial),
        );

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <div className="max-w-[900px]">
        <h1 className="font-serif text-2xl font-bold tracking-tight text-ink">Alertas validadas</h1>
        <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-ink-2">
          Detecciones que una persona ha revisado y aprobado antes de publicarse. Cada una lleva
          el fragmento exacto del texto archivado sobre el que se clasificó, la regla que la
          produjo y la huella del documento, para que se pueda comprobar en la fuente oficial sin
          fiarse de nosotros.
        </p>
        {/*
          El canal de difusión por defecto (ADR 0010), y se explica en vez de poner solo un
          icono: lo que lo hace distinto no es el formato, es que suscribirse no crea ninguna
          lista con tu nombre. Esa frase es la decisión de diseño entera, así que se dice.
        */}
        <p className="mt-3 text-sm text-ink-2">
          <a
            href="/api/alertas.xml"
            type="application/atom+xml"
            className="font-medium text-link hover:text-ink"
          >
            Suscríbete por Atom/RSS
          </a>{" "}
          — sin dar tu correo y sin que sepamos quién eres. No hay lista de suscriptores porque
          estar en ella ya diría algo de ti.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-1.5" role="group" aria-label="Filtrar por clasificación">
        {CLASIFICACIONES.map((opcion) => (
          <button
            key={opcion.valor}
            type="button"
            onClick={() => setClasificacion(opcion.valor)}
            aria-pressed={clasificacion === opcion.valor}
            className={`rounded border px-3 py-1.5 text-xs font-medium ${
              clasificacion === opcion.valor
                ? "border-ink bg-ink text-bg"
                : "border-line-2 bg-surface text-ink-2 hover:border-ink-3 hover:text-ink"
            }`}
          >
            {opcion.etiqueta}
          </button>
        ))}
      </div>

      {estado.fase === "cargando" && <p className="mt-8 text-ink-2">Cargando alertas…</p>}
      {estado.fase === "error" && <p className="mt-8 text-ink-2">{describirError(estado.error)}</p>}

      {estado.fase === "listo" &&
        (() => {
          const alertas = filtrar(estado.datos);
          if (alertas.length === 0) {
            return (
              <div className="mt-8 max-w-[900px] rounded border border-dashed border-line-2 bg-surface p-8">
                <p className="m-0 text-base font-semibold text-ink">
                  Ninguna alerta emitida con estos criterios
                </p>
                <p className="mt-2 max-w-[62ch] text-sm leading-relaxed text-ink-2">
                  Esto significa que nada ha pasado el gate humano todavía, que no es lo mismo que
                  «no hay nada detectado»: el pipeline puede tener detecciones esperando revisión.
                  Ninguna se publica hasta que una persona la apruebe.
                </p>
                <button
                  type="button"
                  onClick={onGoArchivo}
                  className="mt-4 rounded bg-ink px-3.5 py-2 text-sm text-bg"
                >
                  Ver el archivo de documentos
                </button>
              </div>
            );
          }
          return (
            <>
              <div className="mb-3 mt-5 font-mono text-xs text-ink-3">
                {alertas.length} {alertas.length === 1 ? "alerta emitida" : "alertas emitidas"}
                {comunidadInicial && ` · filtradas por ${comunidadInicial}`}
              </div>
              <div className="max-w-[900px]">
                {alertas.map((alerta) => (
                  <AlertCard key={alerta.id} alerta={alerta} />
                ))}
              </div>
            </>
          );
        })()}
    </main>
  );
}
