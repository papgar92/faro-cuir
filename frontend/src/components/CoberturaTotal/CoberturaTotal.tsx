import type { CoberturaApi } from "../../api/client";

/**
 * Cuántas fuentes oficiales se vigilan de las que se conocen. Hoy **2 de 45**.
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

  const { conocidas, vigiladas, ilegibles } = cobertura;
  const pendientes = Math.max(0, conocidas - vigiladas);

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
