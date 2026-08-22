import { useState } from "react";
import { type HallazgoApi, listarHallazgos } from "../api/client";
import { describirError, useRecurso } from "../api/useRecurso";
import { DatosYCita } from "../components/DatosYCita/DatosYCita";
import { HallazgoCard } from "../components/HallazgoCard/HallazgoCard";

/**
 * La superficie pública de **hallazgos históricos** (ADR 0025, decisiones 3 y 4).
 *
 * Pantalla aparte de Alertas, y no por orden ni por sitio en el menú: son dos cosas que afirman
 * cosas distintas. Una alerta dice «una persona lo revisó y decidió publicarlo». Un hallazgo dice
 * «el archivo prueba que esto cambió, otra organización ya lo denunció, y de este proyecto no lo
 * ha mirado nadie». Meterlos en la misma lista con una etiqueta convertiría esa diferencia en algo
 * que se pierde al primer rediseño.
 *
 * Gracias a esa separación la frase de la portada —«nada se publica sin revisión humana»— **sigue
 * siendo literalmente cierta**: un hallazgo no es una publicación del proyecto, es una cita doble.
 *
 * **El estado vacío no es un error y casi nunca es un fallo.** Un hallazgo deja de serlo en cuanto
 * alguien lo aprueba: pasa a la tabla `alerta` y aparece en la otra pantalla. Que esto esté vacío
 * suele significar que la cola está al día, que es la buena noticia y no la mala. La pantalla lo
 * dice con esas palabras en vez de enseñar un vacío mudo.
 */

const CLASIFICACIONES: Array<{ valor: HallazgoApi["clasificacion"] | "todas"; etiqueta: string }> =
  [
    { valor: "todas", etiqueta: "Todos" },
    { valor: "retroceso", etiqueta: "Retrocesos" },
    { valor: "avance", etiqueta: "Avances" },
    { valor: "indeterminado", etiqueta: "Sin signo" },
    { valor: "neutro", etiqueta: "Neutros" },
  ];

export function HallazgosPage() {
  const [clasificacion, setClasificacion] = useState<HallazgoApi["clasificacion"] | "todas">(
    "todas",
  );
  const estado = useRecurso(
    (signal) =>
      listarHallazgos(
        { limite: 100, ...(clasificacion === "todas" ? {} : { clasificacion }) },
        signal,
      ),
    [clasificacion],
  );

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <div className="max-w-[900px]">
        <h1 className="font-serif text-2xl font-bold tracking-tight text-ink">
          Hallazgos del archivo
        </h1>
        <p className="mt-2 max-w-[66ch] text-sm leading-relaxed text-ink-2">
          Cambios normativos que estaban en el archivo sin que nadie los hubiera mirado uno a uno.{" "}
          <strong className="font-semibold text-ink">
            No los ha revisado ninguna persona de este proyecto
          </strong>{" "}
          — a diferencia de las alertas, que sí pasan por revisión antes de publicarse.
        </p>
        <p className="mt-3 max-w-[66ch] text-sm leading-relaxed text-ink-2">
          Si aun así se publican es porque cada uno viene con dos cosas que puedes comprobar por tu
          cuenta y que no dependen de que nos creas: el{" "}
          <strong className="font-semibold text-ink">documento oficial archivado</strong>, con su
          huella y su sello de tiempo, y el{" "}
          <strong className="font-semibold text-ink">enlace a la organización</strong> —FELGTBI+,
          Amnistía Internacional, el propio Ministerio— que ya lo había documentado. Lo que no
          encontrarás aquí es nuestra opinión sobre si está bien o mal.
        </p>
      </div>

      <div
        className="mt-5 flex flex-wrap gap-1.5"
        role="group"
        aria-label="Filtrar por clasificación"
      >
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

      {estado.fase === "cargando" && <p className="mt-8 text-ink-2">Cargando hallazgos…</p>}
      {estado.fase === "error" && <p className="mt-8 text-ink-2">{describirError(estado.error)}</p>}

      {estado.fase === "listo" &&
        (estado.datos.length === 0 ? (
          <div className="mt-8 max-w-[900px] rounded border border-dashed border-line-2 bg-surface p-8">
            <p className="m-0 text-base font-semibold text-ink">
              Ningún hallazgo pendiente ahora mismo
            </p>
            <p className="mt-2 max-w-[62ch] text-sm leading-relaxed text-ink-2">
              Esto suele ser buena señal, no un fallo: un hallazgo deja de aparecer aquí en cuanto
              una persona lo revisa, y entonces pasa a las alertas. Un vacío en esta pantalla
              significa que la cola de revisión está al día.
            </p>
            <p className="mt-2 max-w-[62ch] text-sm leading-relaxed text-ink-2">
              También aparece vacía cuando lo que hay en el archivo todavía no lo ha documentado
              ninguna organización de referencia. En ese caso el cambio sigue detectado y en la
              cola, pero no se publica aquí: sin ese respaldo, lo único que podríamos enseñar
              sería lo que opina un modelo, y eso no lo hacemos.
            </p>
          </div>
        ) : (
          <>
            <div className="mb-3 mt-5 font-mono text-xs text-ink-3">
              {estado.datos.length}{" "}
              {estado.datos.length === 1 ? "hallazgo sin revisar" : "hallazgos sin revisar"}
            </div>
            <div className="max-w-[900px]">
              {estado.datos.map((hallazgo) => (
                <HallazgoCard key={hallazgo.id} hallazgo={hallazgo} />
              ))}
            </div>
            {/* Sin `atom`: los hallazgos todavía no tienen feed propio, y ofrecer uno que no
                existe sería el mismo fallo que las anclas muertas del pie. */}
            <DatosYCita
              json="/api/hallazgos"
              ejemplo={
                estado.datos[0] && {
                  identificador: estado.datos[0].norma.identificador_oficial,
                  sha256: estado.datos[0].texto_archivado?.sha256 ?? null,
                  fecha: estado.datos[0].fecha_publicacion,
                }
              }
            />
          </>
        ))}
    </main>
  );
}
