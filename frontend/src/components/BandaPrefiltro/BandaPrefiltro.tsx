import { useEffect, useState, type ReactNode } from "react";

/**
 * Un grupo del índice del Archivo, plegable, con su recuento.
 *
 * ## Por qué existe: era un fallo de cobertura, no de estética
 *
 * El Archivo listaba las normas **en el orden del sumario oficial** y cortaba en las 60
 * primeras. Medido sobre cuatro boletines del BOE, las normas que el prefiltro NO descartó
 * caían en las posiciones 169/169, 130/130, 207-210/210 y 112/112: **cuatro de cuatro, el
 * 100 % de lo que el pipeline decidió mirar quedaba fuera de lo que la pantalla enseñaba.**
 * El orden administrativo del BOE correlaciona a la inversa con la relevancia — las subastas
 * de Hacienda abren el boletín y los convenios con cláusulas LGTBI lo cierran.
 *
 * La pantalla que existe para demostrar que el archivo es completo era la única que ocultaba
 * lo que importa sin declararlo.
 *
 * ## Las dos reglas de esta pieza, y las dos son de neutralidad
 *
 * 1. **Todas las bandas pesan lo mismo.** Mismo tamaño de letra, mismo color, misma altura de
 *    fila, misma huella visible. Lo único que las distingue es **el orden y el estado de
 *    plegado inicial**. Si «descartada» se pintara como secundaria dejaría de parecer parte
 *    del archivo, y el archivo de la 6.5 lo es todo o no es nada.
 * 2. **Agrupar por `prefiltro_estado` no es un juicio sobre las normas**: es publicar la
 *    decisión que el propio sistema ya tomó y que 7.2 define como «qué entra en el LLM y en
 *    qué orden». Por eso el rótulo dice lo que hizo el prefiltro y nunca lo que la norma vale.
 *
 * Se usa `<details>`/`<summary>` nativo, que es idioma que el proyecto ya usa (`AlertCard`,
 * `HallazgoCard`): sale gratis en teclado y en lectores de pantalla, sin un solo `aria-expanded`
 * escrito a mano.
 */
export function BandaPrefiltro({
  glifo,
  titulo,
  explicacion,
  recuento,
  abierta,
  children,
}: {
  glifo: string;
  titulo: string;
  explicacion: string;
  recuento: number;
  /** Estado inicial. Las descartadas nacen plegadas por volumen, no por peso. */
  abierta: boolean;
  children: ReactNode;
}) {
  // **Las filas de una banda plegada no se montan.** Un `<details>` cerrado igualmente mete sus
  // hijos en el DOM —solo los oculta— y la banda de descartadas de un BOE trae ~330 normas. Con
  // las cuatro bandas eso pasó de las 60 filas de la lista anterior a varios cientos, cada una
  // con su insignia y su huella, y el navegador se quedaba colgado al abrir el boletín de hoy.
  // Se descubrió al mirar la pantalla en el navegador, que es justo para lo que se mira.
  const [desplegada, setDesplegada] = useState(abierta);

  // La banda se abre sola cuando hay una búsqueda activa: si has escrito algo, el resultado no
  // puede quedarse escondido dentro de un cajón cerrado.
  useEffect(() => setDesplegada(abierta), [abierta]);

  return (
    <details
      open={desplegada}
      onToggle={(evento) => setDesplegada(evento.currentTarget.open)}
      className="border-b border-line last:border-b-0"
    >
      <summary className="cursor-pointer list-none px-4 py-2.5 hover:bg-inset [&::-webkit-details-marker]:hidden">
        <span className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <span aria-hidden="true" className="font-mono text-xs text-ink-3">
            {glifo}
          </span>
          <span className="font-mono text-[11px] uppercase tracking-wide text-ink-2">
            {titulo}
          </span>
          <span className="font-mono text-[11px] text-ink">{recuento}</span>
          <span className="ml-auto font-mono text-[10.5px] text-ink-3">
            {desplegada ? "plegar" : "desplegar"}
          </span>
        </span>
        <span className="mt-0.5 block max-w-[60ch] text-[11.5px] leading-snug text-ink-3">
          {explicacion}
        </span>
      </summary>
      {recuento === 0 ? (
        <p className="m-0 px-4 pb-3 pt-1 text-[11.5px] text-ink-3">Ninguna en este documento.</p>
      ) : (
        desplegada && <ul className="m-0 list-none p-0">{children}</ul>
      )}
    </details>
  );
}
