import { useState } from "react";

import type { CambioPreceptoApi } from "../../api/client";

/**
 * Qué decía un precepto y qué dice ahora (ADR 0018).
 *
 * Es la pantalla que el proyecto no podía tener hasta ahora: el BOE modificativo publica la
 * redacción **nueva** y nunca la vieja, así que una alerta podía decir «han modificado el
 * artículo 4» y no podía enseñar de qué a qué. Las dos redacciones salen del texto consolidado
 * del BOE, archivado con su `sha256`.
 *
 * **Se enseñan los dos textos enteros, sin resaltar qué palabras cambian.** No es pereza: un
 * resaltado palabra a palabra lo calcularíamos nosotros, y entonces lo que el lector vería
 * subrayado como «lo que han quitado» sería una interpretación nuestra sobre una cita literal.
 * Poner las dos columnas y dejar leer es lo que corresponde a un sistema que publica el cambio
 * y no el juicio (regla de oro 2). El componente `DiffBlock`, que sí resalta, sigue esperando
 * a que exista esa decisión con su propio criterio.
 *
 * **La huella del consolidado se enseña y se explica.** No es la misma que la del texto
 * publicado: el consolidado es una elaboración posterior de la fuente, y quien quiera rebatir
 * el diff necesita saber contra qué documento contrastarlo.
 *
 * **Se pintan de seis en seis, y eso lo encontró el navegador y no un test.** La reforma
 * madrileña trae 34 preceptos, y varios —el preámbulo entero, por ejemplo— son de miles de
 * caracteres: al abrirlos todos de golpe la pestaña se quedó bloqueada más de treinta segundos.
 * Cada redacción va además en una caja con su propio desplazamiento, para que un precepto largo
 * no entierre a los cinco siguientes. Nada se oculta: se despliega a petición y se dice cuántos
 * quedan.
 */

const POR_TANDA = 6;

interface CambiosPreceptoProps {
  cambios: CambioPreceptoApi[];
}

function Redaccion({
  etiqueta,
  texto,
  vacio,
}: {
  etiqueta: string;
  texto: string | null;
  vacio: string;
}) {
  return (
    <div>
      <div className="border-b border-line px-4 py-2.5">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
          {etiqueta}
        </span>
      </div>
      {texto ? (
        <p className="max-h-80 overflow-y-auto whitespace-pre-wrap p-4 text-sm leading-[1.72] text-ink">
          {texto}
        </p>
      ) : (
        // NULL no es cadena vacía: en una supresión significa que ya no hay texto, y en un alta
        // que no lo había. Decirlo con palabras evita que un hueco se lea como un fallo de carga.
        <p className="p-4 text-sm italic leading-[1.72] text-ink-3">{vacio}</p>
      )}
    </div>
  );
}

export function CambiosPrecepto({ cambios }: CambiosPreceptoProps) {
  const [visibles, setVisibles] = useState(POR_TANDA);

  if (cambios.length === 0) return null;

  const mostrados = cambios.slice(0, visibles);
  const restantes = cambios.length - mostrados.length;

  return (
    <div className="mt-3 space-y-3">
      {mostrados.map((cambio) => (
        <section
          key={`${cambio.norma_afectada}-${cambio.bloque ?? cambio.articulo}`}
          className="overflow-hidden rounded border border-line bg-surface"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line bg-inset px-4 py-2.5">
            <h4 className="text-sm font-semibold text-ink">
              {cambio.articulo || cambio.bloque || "Precepto"}
            </h4>
            <span className="font-mono text-[10.5px] text-ink-3">
              {cambio.norma_afectada}
              {cambio.fecha_vigencia && ` · en vigor desde ${cambio.fecha_vigencia}`}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 sm:divide-x sm:divide-line">
            <Redaccion
              etiqueta="Antes"
              texto={cambio.texto_anterior}
              vacio="No existía: este precepto lo añade esta norma."
            />
            <Redaccion
              etiqueta="Ahora"
              texto={cambio.texto_nuevo}
              vacio="Sin texto: el precepto queda suprimido."
            />
          </div>

          <p className="border-t border-line bg-inset px-4 py-2 font-mono text-[10.5px] text-ink-3">
            Ambas redacciones salen del texto consolidado del BOE, archivado con sha256{" "}
            <span title={cambio.consolidado_sha256}>
              {cambio.consolidado_sha256.slice(0, 12)}…
            </span>
            . El consolidado es una elaboración de la fuente, no el boletín de aquel día.
            {cambio.truncado && " Alguna de las dos redacciones se ha recortado para publicarla."}
          </p>
        </section>
      ))}

      {restantes > 0 && (
        <button
          type="button"
          onClick={() => setVisibles((previo) => previo + POR_TANDA)}
          className="rounded border border-line-2 bg-inset px-2.5 py-1.5 text-xs font-medium text-ink hover:border-line"
        >
          Ver {Math.min(restantes, POR_TANDA)} precepto{restantes > 1 ? "s" : ""} más · quedan{" "}
          {restantes}
        </button>
      )}
    </div>
  );
}
