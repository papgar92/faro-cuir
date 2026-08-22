import type { AlertaApi } from "../../api/client";
import { COLOR_CLASSES, type ColorClasificacion } from "../../lib/classification";
import type { ResumenEstatal } from "../../lib/mapa";

/**
 * Lo que pasa en el **ámbito estatal**, que es el nivel que el mapa por comunidades no puede
 * dibujar.
 *
 * ## Por qué esto no es una silueta de España coloreada
 *
 * Era la idea obvia y se descartó por una razón concreta, no por gusto: colorear una silueta
 * obliga a resumir todas las alertas estatales en **un** color. Con 4 avances y 1 retroceso hay
 * que elegir uno, y la regla de gravedad del proyecto elegiría `retroceso` — la pantalla
 * afirmaría «España: retroceso» teniendo el 80 % de sus alertas en avance. Sería un veredicto
 * nacional que ninguna regla emitió y que nadie aprobó (regla de oro 2), en el píxel más visible
 * de la interfaz.
 *
 * ## Lo que se pinta en su lugar: una marca por alerta
 *
 * Un cuadrado por alerta aprobada, agrupados por signo. No es un porcentaje, no es una barra
 * apilada y no es una media: **cada marca es una alerta concreta que una persona revisó y
 * aprobó**, y a esta escala se pueden contar con el ojo. Da color real a la pantalla sin
 * inventarse una sola fila y sin agregar nada, y sigue funcionando con cincuenta.
 *
 * ## El orden del texto es parte del arreglo
 *
 * Antes esto era un párrafo que empezaba explicando por qué el mapa no puede pintarlo, o sea que
 * el 62 % de lo que el sistema ha llegado a afirmar se presentaba como una limitación del
 * producto. Aquí va **el dato primero y el método después y más pequeño**. La explicación sigue
 * estando —es necesaria— pero deja de ser el titular.
 */

interface PanelEstatalProps {
  resumen: ResumenEstatal;
  /** Para pasar a la pantalla de Alertas, que es donde están enteras. */
  onVerAlertas: () => void;
}

const META_SIGNO: Record<
  AlertaApi["clasificacion"],
  { etiqueta: string; glifo: string; color: ColorClasificacion }
> = {
  avance: { etiqueta: "avance", glifo: "▲", color: "adv" },
  retroceso: { etiqueta: "retroceso", glifo: "▼", color: "reg" },
  neutro: { etiqueta: "neutro", glifo: "●", color: "neu" },
  // `indeterminado` en el color de AVISO y no en el de retroceso: la regla se abstuvo de decir
  // hacia dónde, y teñirlo de rojo emitiría el veredicto del que se abstuvo (7.6).
  indeterminado: { etiqueta: "sin signo", glifo: "?", color: "alr" },
};

export function PanelEstatal({ resumen, onVerAlertas }: PanelEstatalProps) {
  return (
    <section className="mt-4 rounded border border-line bg-inset p-3.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="m-0 text-xs font-semibold uppercase tracking-wide text-ink-2">
          Ámbito estatal · BOE
        </h3>
        <span className="font-mono text-xs text-ink-3">1 de 1 fuente vigilada</span>
      </div>

      {resumen.total === 0 ? (
        <p className="mt-2 text-sm leading-relaxed text-ink-2">
          Ninguna alerta aprobada todavía sobre normativa estatal. Cuando la haya, afectará a todo
          el territorio.
        </p>
      ) : (
        <>
          {/* El pictograma. `aria-hidden` porque justo debajo va el mismo dato en texto: para
              quien usa lector de pantalla, contar cuadrados no aporta nada y el recuento sí. */}
          <div className="mt-3 flex flex-wrap items-end gap-x-5 gap-y-3">
            {resumen.porSigno.map((grupo) => {
              const meta = META_SIGNO[grupo.signo];
              const colores = COLOR_CLASSES[meta.color];
              return (
                <div key={grupo.signo}>
                  <div className="flex flex-wrap gap-1" aria-hidden="true">
                    {grupo.alertas.map((alerta) => (
                      <span
                        key={alerta.id}
                        className={`inline-block h-4 w-4 rounded-[2px] border ${colores.bg} ${colores.border}`}
                      />
                    ))}
                  </div>
                  <p className={`mt-1.5 font-mono text-xs ${colores.text}`}>
                    <span aria-hidden="true">{meta.glifo}</span>{" "}
                    <strong className="font-semibold">{grupo.alertas.length}</strong>{" "}
                    {meta.etiqueta}
                  </p>
                </div>
              );
            })}

            <p className="ml-auto font-mono text-xs text-ink-3">
              <strong className="text-base font-semibold text-ink">{resumen.total}</strong>{" "}
              alerta{resumen.total === 1 ? "" : "s"} aprobada{resumen.total === 1 ? "" : "s"}
            </p>
          </div>

          <ul className="mt-3 flex list-none flex-col gap-1 p-0">
            {resumen.porSigno
              .flatMap((grupo) => grupo.alertas)
              .slice(0, 2)
              .map((alerta) => (
                <li key={alerta.id} className="text-xs leading-snug text-ink-2">
                  <span className="font-mono text-[11px] text-ink-3">
                    {alerta.norma.identificador_oficial}
                  </span>{" "}
                  {alerta.norma.titulo}
                </li>
              ))}
          </ul>

          {resumen.total > 2 && (
            <button
              type="button"
              onClick={onVerAlertas}
              className="mt-2 font-mono text-xs font-medium text-link hover:text-ink"
            >
              ver las {resumen.total} →
            </button>
          )}

          {/* El método, después del dato y en el tamaño del método. */}
          <p className="mt-3 text-xs leading-relaxed text-ink-3">
            Aplica a las diecisiete comunidades. No se pinta en el mapa: colorearlas todas diría
            que hay diecisiete cambios donde hay uno, y pintar una sola sería falso.
          </p>
        </>
      )}
    </section>
  );
}
