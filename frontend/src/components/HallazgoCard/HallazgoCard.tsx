import { formatearFecha, formatearSelloTiempo } from "../../lib/formato";
import { nombreTerritorio } from "../../lib/territorio";
import { reglaPublicada } from "../../lib/reglas";
import type { HallazgoApi } from "../../api/client";

/**
 * Un **hallazgo histórico** (ADR 0025, decisiones 3 y 4). No es una alerta, y la tarjeta tiene
 * que dejarlo claro sin que nadie lea la letra pequeña.
 *
 * ## Lo que esta tarjeta afirma, y lo que no
 *
 * Afirma **dos hechos verificables y ninguno nuestro**:
 *
 * 1. Que el cambio ocurrió — el documento archivado, con su huella y su sello.
 * 2. Que alguien con nombre ya lo denunció — la corroboración, con enlace.
 *
 * No afirma que sea un retroceso, ni que haya que hacer nada. Por eso aquí **no se pinta el
 * semáforo del informe ni su recomendación**: no viajan en la API (ver `HallazgoApi`), y si
 * algún día viajaran seguirían sin pintarse. «Yo publicaría esto» es la opinión de un asistente,
 * y la regla de oro 2 dice que el sistema nunca emite un juicio propio.
 *
 * ## El orden de la tarjeta no es maquetación
 *
 * Va: aviso de que no lo ha revisado nadie → qué norma y qué dice el archivo → **quién más lo ha
 * documentado** → qué lo refutaría. La corroboración va ANTES que cualquier interpretación
 * porque es lo que sostiene que esto se pueda publicar; y la refutación cierra, con el mismo
 * peso visual que el resto y **nunca plegada**, por lo mismo que es obligatoria en el panel: sin
 * ella, un texto que nadie ha revisado se lee como una conclusión.
 *
 * ## Por qué el aviso va arriba y no en un pie
 *
 * Porque lo que distingue esto de una alerta es justo eso, y un aviso que se lee después del
 * contenido llega tarde. Es el mismo criterio que puso el informe de apoyo DEBAJO de la
 * evidencia en el panel: el orden decide qué condiciona a qué.
 */

interface HallazgoCardProps {
  hallazgo: HallazgoApi;
}

export function HallazgoCard({ hallazgo }: HallazgoCardProps) {
  const { informe, norma } = hallazgo;
  const regla = reglaPublicada(hallazgo.regla_aplicada);
  const territorios = hallazgo.normas_vigiladas
    .map((n) => nombreTerritorio(n.ambito))
    .filter((t) => t !== "");

  return (
    <article className="mb-4 rounded border border-line-2 bg-surface">
      {/*
        El aviso. En el color de AVISO y no en el de retroceso: decir «esto no lo ha revisado
        nadie» no es decir «esto es malo». Son cosas distintas y teñirlo de rojo afirmaría un
        signo que este componente no conoce.
      */}
      <p className="m-0 flex flex-wrap items-baseline gap-x-2 rounded-t border-b border-alr bg-alr-bg px-4 py-2 text-xs text-ink">
        <strong className="font-semibold">Hallazgo sin revisar.</strong>
        <span className="text-ink-2">
          Lo preparó {informe.generado_por} el {formatearFecha(informe.generado_en)}. No lo ha
          revisado ninguna persona. Se publica porque el cambio está en el archivo oficial y
          porque otra organización ya lo ha documentado — las dos cosas se pueden comprobar aquí
          abajo.
        </span>
      </p>

      <div className="px-4 py-3.5">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 font-mono text-xs text-ink-3">
          <span>{formatearFecha(hallazgo.fecha_publicacion)}</span>
          <span aria-hidden="true">·</span>
          <span>{norma.identificador_oficial}</span>
          {territorios.length > 0 && (
            <>
              <span aria-hidden="true">·</span>
              <span>{territorios.join(", ")}</span>
            </>
          )}
        </div>

        <h3 className="mt-1.5 font-serif text-base font-semibold leading-snug text-ink">
          {norma.url_texto ? (
            <a href={norma.url_texto} className="text-ink hover:text-link" rel="noreferrer">
              {norma.titulo}
            </a>
          ) : (
            norma.titulo
          )}
        </h3>

        <p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-ink-2">{informe.resumen}</p>

        {informe.a_quien_afecta && (
          <p className="mt-2 max-w-[70ch] text-sm leading-relaxed text-ink-2">
            <strong className="font-semibold text-ink">A quién afecta.</strong>{" "}
            {informe.a_quien_afecta}
          </p>
        )}

        {/* Citas literales del texto archivado. Van en monoespaciada y entrecomilladas para que
            se distingan de la prosa del informe: unas son de la norma y la otra es de un
            asistente, y confundirlas sería lo peor que puede hacer esta pantalla. */}
        {informe.citas.length > 0 && (
          <ul className="mt-3 list-none space-y-2 p-0">
            {informe.citas.map((cita, indice) => (
              <li
                key={indice}
                className="border-l-2 border-line-2 py-0.5 pl-3 font-mono text-xs leading-relaxed text-ink"
              >
                «{cita.texto}»
                {(cita.apartado || cita.version) && (
                  <span className="mt-0.5 block not-italic text-ink-3">
                    {cita.apartado}
                    {cita.apartado && cita.version ? " · " : ""}
                    {cita.version === "vieja"
                      ? "redacción anterior"
                      : cita.version === "nueva"
                        ? "redacción nueva"
                        : ""}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        {/*
          LA CORROBORACIÓN. Es lo que hace publicable un hallazgo que nadie ha revisado
          (decisión 4 del ADR 0025), así que va destacada y nunca plegada. `corroboraciones`
          no puede venir vacía —la consulta del backend no devuelve hallazgos sin ella— pero se
          comprueba igual: si algún día viniera vacía, esta tarjeta no debe inventarse un
          respaldo que no existe.
        */}
        {informe.corroboraciones.length > 0 && (
          <section className="mt-4 rounded border border-line-2 bg-bg p-3">
            <h4 className="m-0 text-xs font-semibold uppercase tracking-wide text-ink-2">
              Quién lo ha documentado ya
            </h4>
            <ul className="mt-2 list-none space-y-2.5 p-0">
              {informe.corroboraciones.map((fuente, indice) => (
                <li key={indice} className="text-sm leading-relaxed text-ink-2">
                  <strong className="font-semibold text-ink">{fuente.organizacion}</strong>
                  {fuente.que_dice && <span> — {fuente.que_dice}</span>}
                  {fuente.url && (
                    <>
                      {" "}
                      <a
                        href={fuente.url}
                        className="font-medium text-link hover:text-ink"
                        rel="noreferrer"
                      >
                        Ver la fuente
                      </a>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/*
          LA REFUTACIÓN. Mismo peso visual que lo demás y jamás plegada, igual que en el panel
          de revisión: es lo que convierte un texto sin revisar en una lista de comprobación en
          vez de en un titular.
        */}
        <section className="mt-3 rounded border border-dashed border-line-2 p-3">
          <h4 className="m-0 text-xs font-semibold uppercase tracking-wide text-ink-2">
            Qué desmontaría esto
          </h4>
          <p className="mt-1.5 max-w-[70ch] text-sm leading-relaxed text-ink-2">
            {informe.refutacion}
          </p>
        </section>

        {/* Qué dice la regla que lo detectó. Aquí importa incluso más que en una alerta: un
            hallazgo no lo ha revisado nadie, así que lo único que lo sostiene es que se pueda
            comprobar entero — y eso incluye el criterio, no solo el texto (7.6). */}
        {regla && (
          <details className="mt-3 rounded border border-line-2 bg-bg px-3 py-2">
            <summary className="cursor-pointer font-mono text-[11px] text-ink-2 hover:text-ink">
              qué dice la regla {regla.id}
            </summary>
            <dl className="mt-2 space-y-2 text-xs leading-relaxed text-ink-2">
              <div>
                <dt className="font-semibold text-ink">Se dispara cuando</dt>
                <dd className="m-0">{regla.enunciado}</dd>
              </div>
              <div>
                <dt className="font-semibold text-ink">Evidencia que exige</dt>
                <dd className="m-0">{regla.evidencia}</dd>
              </div>
              <div>
                <dt className="font-semibold text-ink">Qué signo emite</dt>
                <dd className="m-0">{regla.signo}</dd>
              </div>
            </dl>
          </details>
        )}

        {/* La huella del archivo: es la mitad verificable del hallazgo y por eso se publica
            entera, igual que en una alerta (6.5). */}
        {hallazgo.texto_archivado && (
          <p className="mt-3 break-all font-mono text-[11px] leading-relaxed text-ink-3">
            sha256 {hallazgo.texto_archivado.sha256}
            <span className="block">
              sellado {formatearSelloTiempo(hallazgo.texto_archivado.sello_tiempo)} ·{" "}
              <a
                href={hallazgo.texto_archivado.url_original}
                className="text-link hover:text-ink"
                rel="noreferrer"
              >
                fuente oficial
              </a>
              {hallazgo.regla_aplicada && ` · regla ${hallazgo.regla_aplicada}`}
            </span>
          </p>
        )}
      </div>
    </article>
  );
}
