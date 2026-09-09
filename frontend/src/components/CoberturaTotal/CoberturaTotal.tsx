import type { CoberturaApi } from "../../api/client";

/**
 * Cuántas fuentes oficiales se vigilan de las que se conocen, **y cuáles**.
 *
 * ## Lo que se añadió el 2026-09-06, y por qué
 *
 * El recuento ya estaba. Lo que faltaba era **decir los nombres**: «7 de 61» se lee como una
 * promesa de progreso, mientras que siete boletines con nombre y cincuenta y cuatro en blanco se
 * leen como lo que son. Quien consulte esto tiene derecho a saber si su comunidad está dentro
 * sin deducirlo del color de un mapa.
 *
 * Y con los nombres van dos cosas que no son obvias y que callarlas sería peor:
 *
 * - **Dónde el eje referencial no puede dispararse.** Asturias y Castilla y León no tienen ley
 *   autonómica LGTBI, así que allí no hay norma propia sobre la que detectar una modificación
 *   (7.3). «Castilla y León: 0 alertas» se lee como tranquilidad, y se lee mucho peor.
 * - **De dónde sale la evidencia de cada fuente.** `html` significa que se recorta de una página
 *   de portal y no de un documento estructurado (ADR 0036): un rediseño la puede dejar ilegible
 *   de un día para otro. Es una promesa más débil, y se dice.
 *
 * ## Por qué esto ocupa el sitio bueno
 *
 * Este número estaba en un pie, en el tamaño de una nota al margen, y es el dato que explica la
 * pantalla entera: el mapa tiene quince comunidades sin color **porque hay 43 boletines
 * conocidos sin integrar**, no porque falle nada. Enseñarlo pequeño convertía un hecho medido en
 * una sensación de producto a medias.
 *
 * Puesto así se lee al revés, y esa lectura es la honesta: no es «nos falta cobertura», es «esto
 * es lo que hoy no está mirando nadie». Es el mismo argumento del manifiesto, con un número
 * detrás.
 *
 * ## Una marca por fuente, igual que la banda estatal
 *
 * Mismo principio que `PanelEstatal`: nada de porcentajes ni de barras continuas. Cuarenta y
 * cinco marcas, dos encendidas. Un 4,4 % es una cifra que se olvida; cuarenta y tres huecos en
 * fila se ven.
 */

interface CoberturaTotalProps {
  cobertura: CoberturaApi | undefined;
  onGoArchivo: () => void;
}

export function CoberturaTotal({ cobertura, onGoArchivo }: CoberturaTotalProps) {
  if (!cobertura) return null;

  const { conocidas, vigiladas, ilegibles, fuentes_vigiladas, ccaa_sin_ley_autonomica } = cobertura;
  const pendientes = Math.max(0, conocidas - vigiladas);
  // `?? []` y no un valor por defecto en el tipo: si un día la API dejara de enviarlo, esta
  // sección desaparece en vez de romper la portada entera. Lo que no puede pasar es que se
  // invente una lista.
  const vivas = fuentes_vigiladas ?? [];

  return (
    <section className="border-t border-line p-5">
      <h3 className="m-0 text-xs font-semibold uppercase tracking-wide text-ink-2">
        Fuentes oficiales integradas
      </h3>

      {/* `aria-hidden`: el recuento en texto va justo debajo y dice lo mismo mejor. */}
      <div className="mt-2.5 flex flex-wrap gap-[3px]" aria-hidden="true">
        {Array.from({ length: conocidas }, (_, indice) => (
          <span
            key={indice}
            className={`inline-block h-2.5 w-2.5 rounded-[1px] ${
              indice < vigiladas ? "bg-adv border border-adv" : "bg-surface-2 border border-line-2"
            }`}
          />
        ))}
      </div>

      <p className="mt-2.5 font-mono text-xs text-ink-2">
        <strong className="text-base font-semibold text-ink">{vigiladas}</strong> de {conocidas}{" "}
        · {pendientes} pendientes
      </p>

      <p className="mt-2 text-sm leading-relaxed text-ink-2">
        Ahí es donde hoy <strong className="font-semibold text-ink">no está mirando nadie</strong>.
        No es que en esos territorios no pase nada: es que este proyecto todavía no lee sus
        boletines.
      </p>

      {vivas.length > 0 && (
        // Los nombres. Sin esto la sección dice cuántas y deja al lector sin saber si lo suyo
        // está dentro, que es la única pregunta que se hace quien entra aquí.
        <div className="mt-3">
          <h4 className="m-0 text-xs font-semibold uppercase tracking-wide text-ink-2">
            Las que sí se leen
          </h4>
          <ul className="mt-1.5 list-none space-y-1 p-0">
            {vivas.map((fuente) => (
              <li key={fuente.nombre} className="flex flex-wrap items-baseline gap-x-2 text-sm">
                <span className="text-ink">{fuente.nombre}</span>
                {fuente.formato === "html" && (
                  // Se marca **solo** el nivel más frágil, y no los tres, porque una etiqueta en
                  // cada línea deja de leerse. Lo que hay que poder ver de un vistazo es dónde la
                  // promesa es más débil (ADR 0036).
                  <span
                    className="rounded border border-line-2 px-1 font-mono text-[10px] text-ink-3"
                    title="Su articulado solo se publica como página web: se recorta de un contenedor declarado, y un rediseño del portal puede dejarlo ilegible."
                  >
                    texto de página web
                  </span>
                )}
                <span className="font-mono text-[11px] text-ink-3">
                  {fuente.ultima_publicacion
                    ? `hasta ${fuente.ultima_publicacion}`
                    : "sin boletines todavía"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {ccaa_sin_ley_autonomica > 0 && (
        // El hecho menos obvio de esta pantalla, y el que más se malinterpreta si se calla.
        <p className="mt-3 text-xs leading-relaxed text-ink-2">
          Y en{" "}
          <strong className="font-semibold text-ink">
            {ccaa_sin_ley_autonomica} comunidades sin ley autonómica LGTBI
          </strong>{" "}
          la vigilancia es media aunque su boletín esté integrado: sin norma propia no hay nada
          que alguien pueda modificar, así que ahí solo trabaja el vocabulario. «Cero alertas» en
          esas comunidades no significa lo mismo que en las demás.
        </p>
      )}

      {ilegibles > 0 && (
        // El hueco que no es de cobertura sino nuestro (ADR 0020), y va aparte para no sumarlo a
        // lo anterior: son normas que SÍ hemos descargado y que el pipeline no sabe leer.
        <p className="mt-2 text-xs leading-relaxed text-alr">
          Y {ilegibles} normas descargadas que el pipeline no consigue leer, que es un hueco
          distinto y nuestro.
        </p>
      )}

      <button
        type="button"
        onClick={onGoArchivo}
        className="mt-3 rounded border border-line-2 px-3 py-1.5 text-xs font-medium text-ink-2 hover:border-ink-3 hover:text-ink"
      >
        Ver el archivo de documentos
      </button>
    </section>
  );
}
